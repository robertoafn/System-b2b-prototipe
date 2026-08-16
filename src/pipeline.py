"""Command-line entry point for the V1.0 Core pipeline."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
from time import perf_counter, sleep
from typing import Sequence
from uuid import uuid4

from src.config import ConfigurationError, load_scenario_config
from src.marts.builder import build_and_publish_marts
from src.synthetic.generator import generate_synthetic_data, publish_synthetic_csvs
from src.validation.publisher import validate_and_publish


EXIT_OK = 0
EXIT_CONFIGURATION_ERROR = 2
EXIT_GENERATION_ERROR = 4
EXIT_VALIDATION_FAILED = 5
EXIT_VALIDATION_ERROR = 6
EXIT_MARTS_FAILED = 7
EXIT_MARTS_ERROR = 8
EXIT_PIPELINE_ERROR = 9


def _sanitized_error(exc: Exception) -> str:
    message = " ".join(str(exc).splitlines())
    replacements = (
        (str(Path.cwd().resolve()), "<workspace>"),
        (str(Path.home().resolve()), "<home>"),
    )
    for raw_path, label in replacements:
        message = message.replace(raw_path, label)
    return f"{type(exc).__name__}: {message[:500]}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the synthetic B2B V1.0 analytical dataset."
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to an explicit YAML scenario configuration.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check-config",
        action="store_true",
        help="Validate configuration only; do not generate artifacts.",
    )
    mode.add_argument(
        "--generate-only",
        action="store_true",
        help="Generate and publish synthetic source CSV files only.",
    )
    mode.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate source CSV files and promote successful Parquet outputs.",
    )
    mode.add_argument(
        "--build-marts-only",
        action="store_true",
        help="Build validated star-schema marts and Python KPI controls.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/synthetic"),
        help="Synthetic CSV destination for the full pipeline or --generate-only.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/synthetic"),
        help="Synthetic CSV source used with --validate-only.",
    )
    parser.add_argument(
        "--validated-dir",
        type=Path,
        default=Path("data/validated"),
        help="Validated Parquet destination for validation and the full pipeline.",
    )
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=Path("data/manifest"),
        help="QA, KPI-control, and manifest destination.",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("schemas/data_contract_v1.json"),
        help="Independent data-contract schema used with --validate-only.",
    )
    parser.add_argument(
        "--marts-dir",
        type=Path,
        default=Path("data/marts"),
        help="Analytical Parquet destination for marts and the full pipeline.",
    )
    return parser


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved.name


def _pipeline_staging_path(target: Path, token: str) -> Path:
    resolved = target.resolve()
    if resolved == resolved.parent:
        raise ValueError("pipeline output cannot be a filesystem root")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved.parent / f".{resolved.name}.pipeline-{token}"


def _replace_with_retry(source: Path, target: Path) -> None:
    for attempt in range(20):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == 19:
                raise
            sleep(min(0.1 * (attempt + 1), 0.5))


def _promote_pipeline_outputs(
    staged_targets: Sequence[tuple[Path, Path]],
    token: str,
) -> None:
    backups: dict[Path, Path] = {}
    promoted: list[Path] = []
    try:
        for _, target in staged_targets:
            if target.exists():
                backup = target.parent / f".{target.name}.pipeline-backup-{token}"
                _replace_with_retry(target, backup)
                backups[target] = backup
        for staging, target in staged_targets:
            _replace_with_retry(staging, target)
            promoted.append(target)
    except Exception:
        for target in reversed(promoted):
            if target.exists():
                shutil.rmtree(target)
        for target, backup in backups.items():
            if backup.exists() and not target.exists():
                _replace_with_retry(backup, target)
        raise
    finally:
        for staging, _ in staged_targets:
            if staging.exists():
                shutil.rmtree(staging)
        for backup in backups.values():
            if backup.exists():
                shutil.rmtree(backup)


def _rewrite_final_manifest(
    staged_manifest_dir: Path,
    *,
    synthetic_dir: Path,
    validated_dir: Path,
    marts_dir: Path,
    manifest_dir: Path,
    started: float,
) -> None:
    manifest_path = staged_manifest_dir / "run_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["paths"] = {
        "synthetic_input": _display_path(synthetic_dir),
        "validated_output": _display_path(validated_dir),
        "marts_output": _display_path(marts_dir),
        "manifest_output": _display_path(manifest_dir),
    }
    payload["pipeline"] = {
        "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duration_seconds": round(perf_counter() - started, 6),
        "stages": [
            "generation",
            "validation",
            "marts",
            "kpi_controls",
            "manifest",
        ],
        "status": "passed",
    }
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        config = load_scenario_config(args.config)
    except ConfigurationError as exc:
        print(f"configuration_error: {_sanitized_error(exc)}", file=sys.stderr)
        return EXIT_CONFIGURATION_ERROR

    preflight = {
        "config_sha256": config.config_sha256,
        "data_class": config.data_class,
        "scenario_id": config.scenario_id,
        "status": "config_valid",
    }

    if args.check_config:
        print(json.dumps(preflight, sort_keys=True))
        return EXIT_OK

    if args.generate_only:
        try:
            generated = generate_synthetic_data(config)
            hashes = publish_synthetic_csvs(generated, args.output_dir)
        except Exception as exc:
            print(f"generation_error: {_sanitized_error(exc)}", file=sys.stderr)
            return EXIT_GENERATION_ERROR
        result = {
            "dataset_build_id": generated.dataset_build_id,
            "files": len(hashes),
            "row_counts": {
                name: len(table) for name, table in generated.tables.items()
            },
            "status": "synthetic_published",
        }
        print(json.dumps(result, sort_keys=True))
        return EXIT_OK

    if args.validate_only:
        try:
            run = validate_and_publish(
                config,
                input_dir=args.input_dir,
                validated_dir=args.validated_dir,
                manifest_dir=args.manifest_dir,
                schema_path=args.schema,
            )
        except Exception as exc:
            print(f"validation_error: {_sanitized_error(exc)}", file=sys.stderr)
            return EXIT_VALIDATION_ERROR
        result = {
            "dataset_build_id": run.outcome.dataset_build_id,
            "execution_id": run.execution_id,
            "failed_gates": sum(
                gate.status == "failed" for gate in run.outcome.results
            ),
            "published": run.published,
            "status": run.outcome.status,
            "total_gates": len(run.outcome.results),
        }
        destination = sys.stdout if run.outcome.passed else sys.stderr
        print(json.dumps(result, sort_keys=True), file=destination)
        return EXIT_OK if run.outcome.passed else EXIT_VALIDATION_FAILED

    if args.build_marts_only:
        try:
            run = build_and_publish_marts(
                config,
                validated_dir=args.validated_dir,
                marts_dir=args.marts_dir,
                manifest_dir=args.manifest_dir,
            )
        except Exception as exc:
            print(f"marts_error: {_sanitized_error(exc)}", file=sys.stderr)
            return EXIT_MARTS_ERROR
        result = {
            "dataset_build_id": run.dataset_build_id,
            "failed_gates": sum(gate.status == "failed" for gate in run.results),
            "marts_execution_id": run.marts_execution_id,
            "published": run.published,
            "status": run.status,
            "tables": len(run.mart_hashes),
            "total_gates": len(run.results),
        }
        destination = sys.stdout if run.status == "passed" else sys.stderr
        print(json.dumps(result, sort_keys=True), file=destination)
        return EXIT_OK if run.status == "passed" else EXIT_MARTS_FAILED

    started = perf_counter()
    token = uuid4().hex
    final_synthetic = args.output_dir.resolve()
    final_validated = args.validated_dir.resolve()
    final_marts = args.marts_dir.resolve()
    final_manifest = args.manifest_dir.resolve()
    final_targets = (
        final_synthetic,
        final_validated,
        final_marts,
        final_manifest,
    )
    if len(set(final_targets)) != len(final_targets):
        print(
            "pipeline_error: output directories must be distinct",
            file=sys.stderr,
        )
        return EXIT_PIPELINE_ERROR

    try:
        staged_synthetic = _pipeline_staging_path(final_synthetic, token)
        staged_validated = _pipeline_staging_path(final_validated, token)
        staged_marts = _pipeline_staging_path(final_marts, token)
        staged_manifest = _pipeline_staging_path(final_manifest, token)
    except Exception as exc:
        print(f"pipeline_error: {_sanitized_error(exc)}", file=sys.stderr)
        return EXIT_PIPELINE_ERROR

    staged_targets = (
        (staged_synthetic, final_synthetic),
        (staged_validated, final_validated),
        (staged_marts, final_marts),
        (staged_manifest, final_manifest),
    )

    try:
        generated = generate_synthetic_data(config)
        synthetic_hashes = publish_synthetic_csvs(generated, staged_synthetic)
    except Exception as exc:
        for staging, _ in staged_targets:
            if staging.exists():
                shutil.rmtree(staging)
        print(f"generation_error: {_sanitized_error(exc)}", file=sys.stderr)
        return EXIT_GENERATION_ERROR

    try:
        validation_run = validate_and_publish(
            config,
            input_dir=staged_synthetic,
            validated_dir=staged_validated,
            manifest_dir=staged_manifest,
            schema_path=args.schema,
        )
    except Exception as exc:
        for staging, _ in staged_targets:
            if staging.exists():
                shutil.rmtree(staging)
        print(f"validation_error: {_sanitized_error(exc)}", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    if not validation_run.outcome.passed or not validation_run.published:
        for staging, _ in staged_targets:
            if staging.exists():
                shutil.rmtree(staging)
        result = {
            "dataset_build_id": validation_run.outcome.dataset_build_id,
            "execution_id": validation_run.execution_id,
            "failed_gates": sum(
                gate.status == "failed" for gate in validation_run.outcome.results
            ),
            "published": False,
            "stage": "validation",
            "status": validation_run.outcome.status,
        }
        print(json.dumps(result, sort_keys=True), file=sys.stderr)
        return EXIT_VALIDATION_FAILED

    if validation_run.outcome.dataset_build_id != generated.dataset_build_id:
        for staging, _ in staged_targets:
            if staging.exists():
                shutil.rmtree(staging)
        print(
            "validation_error: dataset_build_id differs from generated data",
            file=sys.stderr,
        )
        return EXIT_VALIDATION_ERROR

    try:
        marts_run = build_and_publish_marts(
            config,
            validated_dir=staged_validated,
            marts_dir=staged_marts,
            manifest_dir=staged_manifest,
        )
    except Exception as exc:
        for staging, _ in staged_targets:
            if staging.exists():
                shutil.rmtree(staging)
        print(f"marts_error: {_sanitized_error(exc)}", file=sys.stderr)
        return EXIT_MARTS_ERROR

    if marts_run.status != "passed" or not marts_run.published:
        for staging, _ in staged_targets:
            if staging.exists():
                shutil.rmtree(staging)
        result = {
            "dataset_build_id": marts_run.dataset_build_id,
            "failed_gates": sum(
                gate.status == "failed" for gate in marts_run.results
            ),
            "marts_execution_id": marts_run.marts_execution_id,
            "published": False,
            "stage": "marts",
            "status": marts_run.status,
        }
        print(json.dumps(result, sort_keys=True), file=sys.stderr)
        return EXIT_MARTS_FAILED

    if marts_run.dataset_build_id != generated.dataset_build_id:
        for staging, _ in staged_targets:
            if staging.exists():
                shutil.rmtree(staging)
        print(
            "marts_error: dataset_build_id differs from generated data",
            file=sys.stderr,
        )
        return EXIT_MARTS_ERROR

    try:
        _rewrite_final_manifest(
            staged_manifest,
            synthetic_dir=final_synthetic,
            validated_dir=final_validated,
            marts_dir=final_marts,
            manifest_dir=final_manifest,
            started=started,
        )
        _promote_pipeline_outputs(staged_targets, token)
    except Exception as exc:
        for staging, _ in staged_targets:
            if staging.exists():
                shutil.rmtree(staging)
        print(f"pipeline_error: {_sanitized_error(exc)}", file=sys.stderr)
        return EXIT_PIPELINE_ERROR

    result = {
        "dataset_build_id": generated.dataset_build_id,
        "generation": {
            "files": len(synthetic_hashes),
            "rows": {
                name: len(table) for name, table in generated.tables.items()
            },
        },
        "manifest": _display_path(final_manifest / "run_manifest.json"),
        "marts": {
            "execution_id": marts_run.marts_execution_id,
            "failed_gates": 0,
            "tables": len(marts_run.mart_hashes),
            "total_gates": len(marts_run.results),
        },
        "status": "passed",
        "validation": {
            "execution_id": validation_run.execution_id,
            "failed_gates": 0,
            "total_gates": len(validation_run.outcome.results),
        },
    }
    print(json.dumps(result, sort_keys=True))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
