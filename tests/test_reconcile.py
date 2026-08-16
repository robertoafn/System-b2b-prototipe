from __future__ import annotations

from copy import deepcopy

from src.reconcile import reconcile_artifacts


def _manifest() -> dict:
    return {
        "status": "passed",
        "scenario_id": "B2B-V1-BASE",
        "seed": 20260813,
        "generator_version": "0.1.0",
        "schema_version": "1.0.0-rc.1",
        "config_sha256": "CONFIG",
        "dataset_build_id": "BLD-TEST",
        "datasets": {"orders": {"rows_written": 1}},
        "control_metrics": {"eligible_orders": 1},
        "quality_summary": {"failed_gates": 0, "passed_gates": 2},
        "marts_quality_summary": {"failed_gates": 0, "passed_gates": 3},
        "marts_build": {"tables": {"fact_orders": 1, "meta_run": 1}},
        "artifacts": {
            "synthetic_csv_sha256": {"orders": "CSV"},
            "validated_parquet_sha256": {"orders": "PARQUET"},
            "marts_deterministic_combined_sha256": "MARTS",
            "marts_parquet_sha256": {
                "fact_orders": "FACT",
                "meta_run": "EXECUTION-VARIANT-A",
            },
        },
    }


def _controls() -> dict:
    return {
        "control_version": "1.0",
        "controls": [{"kpi_id": "KPI-01", "python_control_value": 1.0}],
    }


def test_reconciliation_ignores_execution_variant_meta_run() -> None:
    expected = _manifest()
    candidate = deepcopy(expected)
    candidate["artifacts"]["marts_parquet_sha256"]["meta_run"] = (
        "EXECUTION-VARIANT-B"
    )

    result = reconcile_artifacts(expected, candidate, _controls(), _controls())

    assert result["status"] == "passed"
    assert result["failed_checks"] == 0
    assert result["excluded_execution_variant_artifacts"] == ["meta_run"]


def test_reconciliation_detects_business_artifact_change() -> None:
    expected = _manifest()
    candidate = deepcopy(expected)
    candidate["artifacts"]["marts_deterministic_combined_sha256"] = "CHANGED"

    result = reconcile_artifacts(expected, candidate, _controls(), _controls())

    assert result["status"] == "failed"
    assert result["failed_checks"] == 1
    assert result["failures"][0]["check"] == (
        "artifacts.marts_deterministic_combined_sha256"
    )


def test_reconciliation_detects_kpi_change() -> None:
    candidate_controls = _controls()
    candidate_controls["controls"][0]["python_control_value"] = 2.0

    result = reconcile_artifacts(
        _manifest(), _manifest(), _controls(), candidate_controls
    )

    assert result["status"] == "failed"
    assert result["failures"][0]["check"] == "kpi_controls.controls"
