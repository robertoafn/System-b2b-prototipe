from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

import pytest
import yaml

from src.config import ConfigurationError, load_scenario_config


ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG = ROOT / "config" / "scenario_base.yaml"


def _base_values() -> dict[str, object]:
    loaded = yaml.safe_load(BASE_CONFIG.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


@contextmanager
def _temporary_yaml(values: dict[str, object]) -> Iterator[Path]:
    with TemporaryDirectory(prefix="config-test-", dir=ROOT / "tests") as directory:
        path = Path(directory) / "scenario.yaml"
        path.write_text(yaml.safe_dump(values, sort_keys=False), encoding="utf-8")
        yield path


def test_base_scenario_loads_with_contract_values() -> None:
    config = load_scenario_config(BASE_CONFIG)

    assert config.scenario_id == "B2B-V1-BASE"
    assert config.seed == 20260813
    assert config.customers_exact == 150
    assert config.skus_exact == 30
    assert config.vehicles_exact == 6
    assert config.operational_sites_exact == 1
    assert len(config.config_sha256) == 64


def test_hash_is_independent_of_yaml_key_order() -> None:
    values = _base_values()
    reversed_values = dict(reversed(list(values.items())))

    with _temporary_yaml(reversed_values) as reordered_path:
        assert (
            load_scenario_config(reordered_path).config_sha256
            == load_scenario_config(BASE_CONFIG).config_sha256
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("customers_exact", 149, "approved contract"),
        ("orders_tolerance_pct", 101, "between 0 and 100"),
        ("period_start", "2025/08/01", "YYYY-MM-DD"),
        ("seed", True, "must be an integer"),
        ("data_class", "real", "synthetic"),
    ],
)
def test_invalid_contract_values_are_rejected(
    field: str,
    value: object,
    message: str,
) -> None:
    values = _base_values()
    values[field] = value

    with _temporary_yaml(values) as invalid_path:
        with pytest.raises(ConfigurationError, match=message):
            load_scenario_config(invalid_path)


def test_unknown_fields_are_rejected() -> None:
    values = _base_values()
    values["unapproved_option"] = 1

    with _temporary_yaml(values) as invalid_path:
        with pytest.raises(ConfigurationError, match="unknown configuration fields"):
            load_scenario_config(invalid_path)
