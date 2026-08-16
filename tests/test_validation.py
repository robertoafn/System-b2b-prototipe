from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from typing import Iterator

import pandas as pd
import pytest

from src.config import load_scenario_config
from src.synthetic.generator import generate_synthetic_data, publish_synthetic_csvs
from src.validation.publisher import validate_and_publish
from src.validation.schema import LoadedSource, load_contract_schema, load_source_tables
from src.validation.validator import ValidationOutcome, validate_loaded_source


ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG = ROOT / "config" / "scenario_base.yaml"
SCHEMA_PATH = ROOT / "schemas" / "data_contract_v1.json"


@pytest.fixture(scope="module")
def source_directory() -> Iterator[Path]:
    config = load_scenario_config(BASE_CONFIG)
    generated = generate_synthetic_data(config)
    with TemporaryDirectory(prefix="validation-source-", dir=ROOT / "tests") as directory:
        source = Path(directory) / "synthetic"
        publish_synthetic_csvs(generated, source)
        yield source


@pytest.fixture(scope="module")
def valid_loaded(source_directory: Path) -> LoadedSource:
    return load_source_tables(source_directory, load_contract_schema(SCHEMA_PATH))


@pytest.fixture(scope="module")
def valid_outcome(valid_loaded: LoadedSource) -> ValidationOutcome:
    return validate_loaded_source(
        valid_loaded,
        load_contract_schema(SCHEMA_PATH),
        load_scenario_config(BASE_CONFIG),
    )


def _mutated(loaded: LoadedSource, dataset: str, mutate) -> LoadedSource:
    tables = {name: table.copy(deep=True) for name, table in loaded.tables.items()}
    mutate(tables[dataset])
    return LoadedSource(tables=tables, findings=())


def _failed_gate(outcome: ValidationOutcome, gate_id: str) -> bool:
    return any(
        result.gate_id == gate_id and result.status == "failed"
        for result in outcome.results
    )


def test_independent_schema_covers_all_source_datasets() -> None:
    schema = load_contract_schema(SCHEMA_PATH)

    assert schema.schema_version == "1.0.0-rc.1"
    assert set(schema.datasets) == {
        "customers", "products", "locations", "operational_sites", "vehicles",
        "orders", "order_lines", "inventory", "deliveries", "delivery_lines",
        "cost_activities",
    }


def test_valid_source_passes_all_gates(valid_outcome: ValidationOutcome) -> None:
    assert valid_outcome.passed
    assert len(valid_outcome.results) >= 60
    assert all(result.status == "passed" for result in valid_outcome.results)
    assert valid_outcome.metrics["row_counts"]["orders"] == 4000
    assert valid_outcome.metrics["row_counts"]["order_lines"] == 10000
    assert valid_outcome.metrics["eligible_orders"] == 4000
    assert min(valid_outcome.metrics["customer_quadrant_counts"].values()) >= 5
    assert valid_outcome.metrics["control_totals"]["recognized_net_sales"] > 0


@pytest.mark.parametrize(
    ("dataset", "gate_id", "mutation"),
    [
        (
            "customers",
            "pk.customers",
            lambda table: table.loc.__setitem__(1, table.loc[0]),
        ),
        (
            "orders",
            "fk.orders.customer_id",
            lambda table: table.loc.__setitem__((0, "customer_id"), "CUS-SYN-999"),
        ),
        (
            "delivery_lines",
            "quantity.no_overdelivery",
            lambda table: table.loc.__setitem__((0, "delivered_quantity"), 1_000_000),
        ),
        (
            "deliveries",
            "time.delivery_event",
            lambda table: table.loc.__setitem__(
                (0, "delivery_datetime"), table.loc[0, "dispatch_datetime"] - pd.Timedelta(hours=1)
            ),
        ),
        (
            "order_lines",
            "economics.net_unit_price",
            lambda table: table.loc.__setitem__(
                (0, "net_unit_price"), table.loc[0, "net_unit_price"] + 10
            ),
        ),
        (
            "products",
            "provenance.operational",
            lambda table: table.loc.__setitem__((0, "is_synthetic"), False),
        ),
    ],
)
def test_invalid_fixtures_fail_the_expected_gate(
    valid_loaded: LoadedSource,
    dataset: str,
    gate_id: str,
    mutation,
) -> None:
    outcome = validate_loaded_source(
        _mutated(valid_loaded, dataset, mutation),
        load_contract_schema(SCHEMA_PATH),
        load_scenario_config(BASE_CONFIG),
    )

    assert not outcome.passed
    assert _failed_gate(outcome, gate_id)


def test_schema_violation_fails_without_running_business_gates(
    source_directory: Path,
) -> None:
    with TemporaryDirectory(prefix="invalid-schema-", dir=ROOT / "tests") as directory:
        copied = Path(directory) / "synthetic"
        shutil.copytree(source_directory, copied)
        orders = pd.read_csv(copied / "orders.csv")
        orders = orders.drop(columns=["order_status"])
        orders.to_csv(copied / "orders.csv", index=False, lineterminator="\n")
        schema = load_contract_schema(SCHEMA_PATH)
        loaded = load_source_tables(copied, schema)
        outcome = validate_loaded_source(
            loaded,
            schema,
            load_scenario_config(BASE_CONFIG),
        )

        assert not outcome.passed
        assert _failed_gate(outcome, "schema.orders")
        assert all(result.category == "schema" for result in outcome.results)


def test_successful_publication_is_repeatable_and_inspectable(
    source_directory: Path,
) -> None:
    config = load_scenario_config(BASE_CONFIG)
    with TemporaryDirectory(prefix="validation-publish-", dir=ROOT / "tests") as directory:
        root = Path(directory)
        validated = root / "validated"
        manifest = root / "manifest"
        first = validate_and_publish(
            config, source_directory, validated, manifest, SCHEMA_PATH
        )
        second = validate_and_publish(
            config, source_directory, validated, manifest, SCHEMA_PATH
        )

        assert first.published and second.published
        assert first.validated_hashes == second.validated_hashes
        assert len(list(validated.glob("*.parquet"))) == 11
        report = json.loads((manifest / "quality_report.json").read_text(encoding="utf-8"))
        run_manifest = json.loads(
            (manifest / "run_manifest.json").read_text(encoding="utf-8")
        )
        assert report["status"] == "passed"
        assert report["summary"]["failed_gates"] == 0
        assert run_manifest["status"] == "passed"
        assert run_manifest["dataset_build_id"] == first.outcome.dataset_build_id
        assert set(run_manifest["runtime_versions"]) == {
            "python", "numpy", "pandas", "pyarrow", "python_dateutil",
            "pyyaml", "tzdata",
        }
        for name, expected_rows in first.outcome.metrics["row_counts"].items():
            assert len(pd.read_parquet(validated / f"{name}.parquet")) == expected_rows


def test_failed_validation_preserves_previous_validated_build(
    source_directory: Path,
) -> None:
    config = load_scenario_config(BASE_CONFIG)
    with TemporaryDirectory(prefix="validation-isolation-", dir=ROOT / "tests") as directory:
        root = Path(directory)
        source = root / "synthetic"
        validated = root / "validated"
        manifest = root / "manifest"
        shutil.copytree(source_directory, source)
        successful = validate_and_publish(
            config, source, validated, manifest, SCHEMA_PATH
        )
        manifest_before = (manifest / "run_manifest.json").read_bytes()
        parquet_before = successful.validated_hashes

        orders = pd.read_csv(source / "orders.csv")
        orders.loc[0, "customer_id"] = "CUS-SYN-999"
        orders.to_csv(source / "orders.csv", index=False, lineterminator="\n")
        failed = validate_and_publish(config, source, validated, manifest, SCHEMA_PATH)

        assert not failed.published
        assert not failed.outcome.passed
        assert (manifest / "run_manifest.json").read_bytes() == manifest_before
        current_hashes = {
            path.stem: __import__("hashlib").sha256(path.read_bytes()).hexdigest().upper()
            for path in validated.glob("*.parquet")
        }
        assert current_hashes == parquet_before
        assert len(list((manifest / "failures").glob("*.json"))) == 1
