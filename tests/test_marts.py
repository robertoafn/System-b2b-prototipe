from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile

import pandas as pd
import pytest

from src.config import load_scenario_config
from src.marts.builder import (
    MART_TABLES,
    MartsBuildError,
    _load_validated_inputs,
    build_and_publish_marts,
    build_mart_tables,
    calculate_kpi_controls,
    validate_mart_tables,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_scenario_config(ROOT / "config" / "scenario_base.yaml")
VALIDATED = ROOT / "data" / "validated"
MANIFEST = ROOT / "data" / "manifest"


@pytest.fixture
def workspace_tmp_path():
    path = Path(tempfile.mkdtemp(prefix="marts-test-", dir=ROOT / "tests"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(scope="module")
def source_bundle():
    return _load_validated_inputs(CONFIG, VALIDATED, MANIFEST)


@pytest.fixture(scope="module")
def built_marts(source_bundle):
    tables, manifest, quality = source_bundle
    return build_mart_tables(tables, CONFIG, manifest, quality)


def test_builds_exact_canonical_star_schema(built_marts, source_bundle) -> None:
    source, _, _ = source_bundle
    assert set(built_marts) == set(MART_TABLES) - {"qa_results"}
    assert len(built_marts["fact_orders"]) == len(source["orders"])
    assert len(built_marts["fact_order_lines"]) == len(source["order_lines"])
    assert len(built_marts["fact_deliveries"]) == len(source["deliveries"])
    assert len(built_marts["fact_delivery_lines"]) == len(source["delivery_lines"])
    assert len(built_marts["fact_inventory"]) == len(source["inventory"])
    assert len(built_marts["fact_cost_to_serve"]) == len(source["cost_activities"])


def test_dimensions_and_optional_vehicle_are_conformed(built_marts) -> None:
    key_pairs = (
        ("dim_customer", "customer_key", "customer_id"),
        ("dim_product", "product_key", "sku_id"),
        ("dim_location", "location_key", "location_id"),
        ("dim_operational_site", "site_key", "site_id"),
        ("dim_vehicle", "vehicle_key", "vehicle_id"),
        ("dim_date", "date_key", "date"),
    )
    for table_name, surrogate, business in key_pairs:
        table = built_marts[table_name]
        assert table[surrogate].is_unique
        assert table[business].is_unique
        assert table[surrogate].notna().all()
        assert table[business].notna().all()

    vehicles = built_marts["dim_vehicle"]
    assert len(vehicles) == CONFIG.vehicles_exact + 1
    assert vehicles.loc[vehicles["vehicle_key"].eq(0), "vehicle_id"].item() == "N/A"
    order_level_costs = built_marts["fact_cost_to_serve"]["delivery_id"].isna()
    assert built_marts["fact_cost_to_serve"].loc[
        order_level_costs, "vehicle_key"
    ].eq(0).all()


def test_mart_gates_and_kpi_controls_reconcile(built_marts, source_bundle) -> None:
    source, manifest, _ = source_bundle
    results = validate_mart_tables(built_marts, source, manifest)
    assert len(results) == 91
    assert all(result.status == "passed" for result in results)

    controls = {
        item["kpi_id"]: item["python_control_value"]
        for item in calculate_kpi_controls(built_marts)
    }
    assert len(controls) == 17
    assert controls["KPI-01"] == pytest.approx(14_486_600_352.07, abs=0.01)
    assert controls["KPI-04"] == pytest.approx(2_082_958_305.74, abs=0.01)
    assert controls["KPI-05"] == pytest.approx(3_554_243_079.01, abs=0.01)
    assert controls["KPI-08"] == pytest.approx(0.7, abs=1e-9)
    assert controls["KPI-09"] == pytest.approx(0.9257752874732879, abs=1e-9)
    assert controls["KPI-11"] == pytest.approx(0.0200913242, abs=1e-9)
    assert controls["KPI-17"] == 150


def test_product_attribution_is_not_added_to_cts_or_mc_cts(built_marts) -> None:
    assert "product_key" not in built_marts["fact_orders"].columns
    assert "product_key" not in built_marts["fact_cost_to_serve"].columns
    assert "mc_cts_amount" not in built_marts["fact_delivery_lines"].columns
    assert "recognized_net_sales" in built_marts["fact_delivery_lines"].columns


def test_validation_detects_an_economic_reconciliation_error(
    built_marts, source_bundle
) -> None:
    source, manifest, _ = source_bundle
    altered = {name: table.copy() for name, table in built_marts.items()}
    altered["fact_orders"].loc[0, "recognized_net_sales"] += 1.00

    failed = {
        result.gate_id
        for result in validate_mart_tables(altered, source, manifest)
        if result.status == "failed"
    }
    assert "reconcile.orders.recognized_net_sales" in failed
    assert "formula.orders.mc_cts" in failed


def test_publication_is_repeatable_and_emits_complete_evidence(
    workspace_tmp_path,
) -> None:
    first_manifest = workspace_tmp_path / "manifest-first"
    second_manifest = workspace_tmp_path / "manifest-second"
    shutil.copytree(MANIFEST, first_manifest)
    shutil.copytree(MANIFEST, second_manifest)
    first = build_and_publish_marts(
        CONFIG, VALIDATED, workspace_tmp_path / "marts-first", first_manifest
    )
    second = build_and_publish_marts(
        CONFIG, VALIDATED, workspace_tmp_path / "marts-second", second_manifest
    )

    assert first.published and second.published
    assert first.mart_hashes == second.mart_hashes
    assert set(first.mart_hashes) == set(MART_TABLES)
    first_run_manifest = json.loads(
        (first_manifest / "run_manifest.json").read_text(encoding="utf-8")
    )
    expected_deterministic_hash = first_run_manifest["artifacts"][
        "marts_deterministic_combined_sha256"
    ]
    assert len(expected_deterministic_hash) == 64
    report = json.loads(
        (first_manifest / "marts_quality_report.json").read_text(encoding="utf-8")
    )
    controls = json.loads(
        (first_manifest / "kpi_controls.json").read_text(encoding="utf-8")
    )
    qa_results = pd.read_parquet(
        workspace_tmp_path / "marts-first" / "qa_results.parquet"
    )
    assert report["summary"] == {
        "failed_gates": 0,
        "passed_gates": 91,
        "total_gates": 91,
    }
    assert len(controls["controls"]) == 17
    assert len(qa_results) == 93 + 91


def test_checksum_mismatch_blocks_mart_build(workspace_tmp_path) -> None:
    altered_validated = workspace_tmp_path / "validated"
    shutil.copytree(VALIDATED, altered_validated)
    with (altered_validated / "orders.parquet").open("ab") as target:
        target.write(b"tampered")
    copied_manifest = workspace_tmp_path / "manifest"
    shutil.copytree(MANIFEST, copied_manifest)

    with pytest.raises(MartsBuildError, match="checksum mismatch: orders"):
        build_and_publish_marts(
            CONFIG, altered_validated, workspace_tmp_path / "marts", copied_manifest
        )
    assert not (workspace_tmp_path / "marts").exists()
