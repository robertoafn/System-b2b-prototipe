"""Load and validate deterministic scenario configuration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml


class ConfigurationError(ValueError):
    """Raised when a scenario configuration violates the contract."""


@dataclass(frozen=True)
class ScenarioConfig:
    """Validated configuration used by every pipeline stage."""

    scenario_id: str
    data_class: str
    seed: int
    period_start: date
    period_end: date
    timezone: str
    currency: str
    customers_exact: int
    skus_exact: int
    vehicles_exact: int
    operational_sites_exact: int
    orders_target: int
    orders_tolerance_pct: int
    order_lines_target: int
    order_lines_tolerance_pct: int
    generator_version: str
    schema_version: str
    config_sha256: str


_FIELD_NAMES = {
    "scenario_id",
    "data_class",
    "seed",
    "period_start",
    "period_end",
    "timezone",
    "currency",
    "customers_exact",
    "skus_exact",
    "vehicles_exact",
    "operational_sites_exact",
    "orders_target",
    "orders_tolerance_pct",
    "order_lines_target",
    "order_lines_tolerance_pct",
    "generator_version",
    "schema_version",
}

_INTEGER_FIELDS = {
    "seed",
    "customers_exact",
    "skus_exact",
    "vehicles_exact",
    "operational_sites_exact",
    "orders_target",
    "orders_tolerance_pct",
    "order_lines_target",
    "order_lines_tolerance_pct",
}

_POSITIVE_FIELDS = {
    "customers_exact",
    "skus_exact",
    "vehicles_exact",
    "operational_sites_exact",
    "orders_target",
    "order_lines_target",
}

_BASE_EXPECTATIONS: Mapping[str, Any] = {
    "data_class": "synthetic",
    "seed": 20260813,
    "period_start": "2025-08-01",
    "period_end": "2026-07-31",
    "timezone": "America/Santiago",
    "currency": "CLP",
    "customers_exact": 150,
    "skus_exact": 30,
    "vehicles_exact": 6,
    "operational_sites_exact": 1,
    "orders_target": 4000,
    "orders_tolerance_pct": 5,
    "order_lines_target": 10000,
    "order_lines_tolerance_pct": 10,
    "generator_version": "0.1.0",
    "schema_version": "1.0.0-rc.1",
}


def _canonical_sha256(values: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        values,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest().upper()


def _require_string(values: Mapping[str, Any], field: str) -> str:
    value = values[field]
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{field} must be a non-empty string")
    return value


def _require_integer(values: Mapping[str, Any], field: str) -> int:
    value = values[field]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError(f"{field} must be an integer")
    return value


def _parse_date(values: Mapping[str, Any], field: str) -> date:
    value = _require_string(values, field)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ConfigurationError(f"{field} must use YYYY-MM-DD") from exc


def _validate_shape(values: Mapping[str, Any]) -> None:
    keys = set(values)
    missing = sorted(_FIELD_NAMES - keys)
    unknown = sorted(keys - _FIELD_NAMES)
    if missing:
        raise ConfigurationError(f"missing configuration fields: {', '.join(missing)}")
    if unknown:
        raise ConfigurationError(f"unknown configuration fields: {', '.join(unknown)}")


def _validate_base_scenario(values: Mapping[str, Any]) -> None:
    if values["scenario_id"] != "B2B-V1-BASE":
        return
    drift = [
        field
        for field, expected in _BASE_EXPECTATIONS.items()
        if values[field] != expected
    ]
    if drift:
        raise ConfigurationError(
            "B2B-V1-BASE differs from the approved contract: " + ", ".join(drift)
        )


def load_scenario_config(path: str | Path) -> ScenarioConfig:
    """Load a YAML file, enforce its schema, and return a stable config hash."""

    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigurationError(f"configuration file not found: {config_path}")

    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"cannot read configuration: {exc}") from exc

    if not isinstance(loaded, dict):
        raise ConfigurationError("configuration root must be a mapping")

    values: Mapping[str, Any] = loaded
    _validate_shape(values)

    for field in _INTEGER_FIELDS:
        _require_integer(values, field)
    for field in _POSITIVE_FIELDS:
        if values[field] <= 0:
            raise ConfigurationError(f"{field} must be greater than zero")
    for field in ("orders_tolerance_pct", "order_lines_tolerance_pct"):
        if not 0 <= values[field] <= 100:
            raise ConfigurationError(f"{field} must be between 0 and 100")

    period_start = _parse_date(values, "period_start")
    period_end = _parse_date(values, "period_end")
    if period_start > period_end:
        raise ConfigurationError("period_start must not be after period_end")

    scenario_id = _require_string(values, "scenario_id")
    data_class = _require_string(values, "data_class")
    timezone = _require_string(values, "timezone")
    currency = _require_string(values, "currency")
    generator_version = _require_string(values, "generator_version")
    schema_version = _require_string(values, "schema_version")

    if data_class != "synthetic":
        raise ConfigurationError("data_class must be synthetic in V1.0 Core")
    if len(currency) != 3 or currency != currency.upper():
        raise ConfigurationError("currency must be a three-letter uppercase code")

    _validate_base_scenario(values)

    return ScenarioConfig(
        scenario_id=scenario_id,
        data_class=data_class,
        seed=values["seed"],
        period_start=period_start,
        period_end=period_end,
        timezone=timezone,
        currency=currency,
        customers_exact=values["customers_exact"],
        skus_exact=values["skus_exact"],
        vehicles_exact=values["vehicles_exact"],
        operational_sites_exact=values["operational_sites_exact"],
        orders_target=values["orders_target"],
        orders_tolerance_pct=values["orders_tolerance_pct"],
        order_lines_target=values["order_lines_target"],
        order_lines_tolerance_pct=values["order_lines_tolerance_pct"],
        generator_version=generator_version,
        schema_version=schema_version,
        config_sha256=_canonical_sha256(values),
    )
