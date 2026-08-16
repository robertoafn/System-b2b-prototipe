"""Reconcile a candidate pipeline build with the committed release baseline.

Execution metadata is intentionally excluded: ``meta_run`` contains the current
execution identifier and timestamp. Business tables, source/validated hashes,
quality gates, and KPI controls must remain deterministic.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence


EXIT_OK = 0
EXIT_RECONCILIATION_FAILED = 1
EXIT_INPUT_ERROR = 2


class ReconciliationError(ValueError):
    """Raised when release artifacts do not reconcile."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReconciliationError(f"Cannot read JSON artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise ReconciliationError(f"JSON artifact must contain an object: {path}")
    return payload


def _required(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            raise ReconciliationError(f"Missing required field: {path}")
        value = value[part]
    return value


def _assert_equal(
    failures: list[dict[str, Any]],
    name: str,
    expected: Any,
    candidate: Any,
) -> None:
    if expected != candidate:
        failures.append(
            {
                "check": name,
                "expected": expected,
                "candidate": candidate,
            }
        )


def reconcile_artifacts(
    expected_manifest: dict[str, Any],
    candidate_manifest: dict[str, Any],
    expected_controls: dict[str, Any],
    candidate_controls: dict[str, Any],
) -> dict[str, Any]:
    """Return a machine-readable reconciliation result."""
    failures: list[dict[str, Any]] = []

    for manifest_name, manifest in (
        ("expected", expected_manifest),
        ("candidate", candidate_manifest),
    ):
        if _required(manifest, "status") != "passed":
            failures.append(
                {
                    "check": f"{manifest_name}_manifest_status",
                    "expected": "passed",
                    "candidate": _required(manifest, "status"),
                }
            )
        for quality_path in ("quality_summary", "marts_quality_summary"):
            failed = _required(manifest, f"{quality_path}.failed_gates")
            if failed != 0:
                failures.append(
                    {
                        "check": f"{manifest_name}_{quality_path}_failed_gates",
                        "expected": 0,
                        "candidate": failed,
                    }
                )

    comparable_fields = (
        "scenario_id",
        "seed",
        "generator_version",
        "schema_version",
        "config_sha256",
        "dataset_build_id",
        "datasets",
        "control_metrics",
        "quality_summary",
        "marts_quality_summary",
        "marts_build.tables",
        "artifacts.synthetic_csv_sha256",
        "artifacts.validated_parquet_sha256",
        "artifacts.marts_deterministic_combined_sha256",
    )
    for field in comparable_fields:
        _assert_equal(
            failures,
            field,
            _required(expected_manifest, field),
            _required(candidate_manifest, field),
        )

    _assert_equal(
        failures,
        "kpi_controls.control_version",
        _required(expected_controls, "control_version"),
        _required(candidate_controls, "control_version"),
    )
    _assert_equal(
        failures,
        "kpi_controls.controls",
        _required(expected_controls, "controls"),
        _required(candidate_controls, "controls"),
    )

    return {
        "status": "passed" if not failures else "failed",
        "dataset_build_id": candidate_manifest.get("dataset_build_id"),
        "checks": len(comparable_fields) + 8,
        "failed_checks": len(failures),
        "failures": failures,
        "excluded_execution_variant_artifacts": ["meta_run"],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reconcile a candidate pipeline build against a known baseline."
    )
    parser.add_argument("--expected-manifest", type=Path, required=True)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--expected-controls", type=Path, required=True)
    parser.add_argument("--candidate-controls", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = reconcile_artifacts(
            _read_json(args.expected_manifest),
            _read_json(args.candidate_manifest),
            _read_json(args.expected_controls),
            _read_json(args.candidate_controls),
        )
    except ReconciliationError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return EXIT_INPUT_ERROR

    print(json.dumps(result, indent=2, sort_keys=True))
    return EXIT_OK if result["status"] == "passed" else EXIT_RECONCILIATION_FAILED


if __name__ == "__main__":
    sys.exit(main())
