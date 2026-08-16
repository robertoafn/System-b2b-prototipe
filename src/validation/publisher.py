"""Validation orchestration, atomic Parquet promotion, and QA evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
from time import perf_counter, sleep
from typing import Any, Mapping
from uuid import uuid4

import numpy as np
import pandas as pd
import pyarrow
import dateutil
import tzdata
import yaml

from src.config import ScenarioConfig
from src.validation.schema import load_contract_schema, load_source_tables
from src.validation.validator import ValidationOutcome, validate_loaded_source


@dataclass(frozen=True)
class ValidationRun:
    execution_id: str
    outcome: ValidationOutcome
    published: bool
    source_hashes: Mapping[str, str]
    validated_hashes: Mapping[str, str]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved.name


def _quality_payload(
    outcome: ValidationOutcome,
    execution_id: str,
    generated_at: str,
) -> dict[str, Any]:
    failed = [result for result in outcome.results if result.status == "failed"]
    severity_counts: dict[str, int] = {}
    for result in failed:
        severity_counts[result.severity] = severity_counts.get(result.severity, 0) + 1
    return {
        "report_version": "1.0",
        "execution_id": execution_id,
        "generated_at": generated_at,
        "dataset_build_id": outcome.dataset_build_id,
        "schema_version": outcome.schema_version,
        "status": outcome.status,
        "summary": {
            "total_gates": len(outcome.results),
            "passed_gates": len(outcome.results) - len(failed),
            "failed_gates": len(failed),
            "failed_by_severity": severity_counts,
        },
        "metrics": outcome.metrics,
        "results": [result.as_dict() for result in outcome.results],
    }


def _runtime_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "pyarrow": pyarrow.__version__,
        "python_dateutil": dateutil.__version__,
        "pyyaml": yaml.__version__,
        "tzdata": tzdata.__version__,
    }


def _atomic_promote_directories(
    staged_targets: list[tuple[Path, Path]],
    token: str,
) -> None:
    def replace_with_retry(source: Path, target: Path) -> None:
        for attempt in range(20):
            try:
                os.replace(source, target)
                return
            except PermissionError:
                if attempt == 19:
                    raise
                sleep(min(0.1 * (attempt + 1), 0.5))

    backups: dict[Path, Path] = {}
    promoted: list[Path] = []
    try:
        for _, target in staged_targets:
            if target.exists():
                backup = target.parent / f".{target.name}.backup-{token}"
                replace_with_retry(target, backup)
                backups[target] = backup
        for staging, target in staged_targets:
            replace_with_retry(staging, target)
            promoted.append(target)
    except Exception:
        for target in reversed(promoted):
            if target.exists():
                shutil.rmtree(target)
        for target, backup in backups.items():
            if backup.exists() and not target.exists():
                replace_with_retry(backup, target)
        raise
    finally:
        for staging, _ in staged_targets:
            if staging.exists():
                shutil.rmtree(staging)
        for backup in backups.values():
            if backup.exists():
                shutil.rmtree(backup)


def _publish_failure_report(
    manifest_dir: Path,
    payload: Mapping[str, Any],
    execution_id: str,
) -> None:
    failure_dir = manifest_dir / "failures"
    failure_dir.mkdir(parents=True, exist_ok=True)
    final_path = failure_dir / f"{execution_id}.json"
    temporary = failure_dir / f".{execution_id}.tmp"
    _write_json(temporary, payload)
    os.replace(temporary, final_path)


def validate_and_publish(
    config: ScenarioConfig,
    input_dir: str | Path,
    validated_dir: str | Path,
    manifest_dir: str | Path,
    schema_path: str | Path,
) -> ValidationRun:
    """Validate source CSVs and promote Parquet plus evidence only on full success."""

    started = perf_counter()
    execution_id = "EXE-" + uuid4().hex.upper()
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    input_path = Path(input_dir).resolve()
    validated_path = Path(validated_dir).resolve()
    manifest_path = Path(manifest_dir).resolve()
    schema = load_contract_schema(schema_path)
    loaded = load_source_tables(input_path, schema)
    outcome = validate_loaded_source(loaded, schema, config)
    source_hashes = {
        name: _sha256(input_path / f"{name}.csv")
        for name in schema.datasets
        if (input_path / f"{name}.csv").is_file()
    }
    quality_payload = _quality_payload(outcome, execution_id, generated_at)

    if not outcome.passed:
        _publish_failure_report(manifest_path, quality_payload, execution_id)
        return ValidationRun(
            execution_id=execution_id,
            outcome=outcome,
            published=False,
            source_hashes=source_hashes,
            validated_hashes={},
        )

    token = uuid4().hex
    validated_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    staged_validated = validated_path.parent / f".{validated_path.name}.staging-{token}"
    staged_manifest = manifest_path.parent / f".{manifest_path.name}.staging-{token}"
    staged_validated.mkdir(parents=False, exist_ok=False)
    staged_manifest.mkdir(parents=False, exist_ok=False)
    validated_hashes: dict[str, str] = {}

    try:
        for name, table in outcome.tables.items():
            output = staged_validated / f"{name}.parquet"
            table.to_parquet(
                output,
                index=False,
                engine="pyarrow",
                compression="snappy",
            )
            validated_hashes[name] = _sha256(output)

        quality_path = staged_manifest / "quality_report.json"
        _write_json(quality_path, quality_payload)
        quality_hash = _sha256(quality_path)
        duration = round(perf_counter() - started, 6)
        row_counts = {
            name: {
                "rows_read": len(table),
                "rows_written": len(table),
                "rows_rejected": 0,
                "rejection_reasons": [],
            }
            for name, table in outcome.tables.items()
        }
        manifest_payload = {
            "manifest_version": "1.0",
            "execution_id": execution_id,
            "executed_at": generated_at,
            "execution_duration_seconds": duration,
            "status": "passed",
            "error": None,
            "scenario_id": config.scenario_id,
            "data_class": config.data_class,
            "seed": config.seed,
            "generator_version": config.generator_version,
            "schema_version": schema.schema_version,
            "config_sha256": config.config_sha256,
            "dataset_build_id": outcome.dataset_build_id,
            "paths": {
                "synthetic_input": _display_path(input_path),
                "validated_output": _display_path(validated_path),
                "manifest_output": _display_path(manifest_path),
            },
            "datasets": row_counts,
            "artifacts": {
                "synthetic_csv_sha256": source_hashes,
                "validated_parquet_sha256": validated_hashes,
                "quality_report_sha256": quality_hash,
            },
            "quality_summary": quality_payload["summary"],
            "control_metrics": outcome.metrics,
            "runtime_versions": _runtime_versions(),
        }
        _write_json(staged_manifest / "run_manifest.json", manifest_payload)
        _atomic_promote_directories(
            [
                (staged_validated, validated_path),
                (staged_manifest, manifest_path),
            ],
            token,
        )
    except Exception:
        if staged_validated.exists():
            shutil.rmtree(staged_validated)
        if staged_manifest.exists():
            shutil.rmtree(staged_manifest)
        raise

    return ValidationRun(
        execution_id=execution_id,
        outcome=outcome,
        published=True,
        source_hashes=source_hashes,
        validated_hashes=validated_hashes,
    )
