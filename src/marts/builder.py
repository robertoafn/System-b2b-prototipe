"""Build, validate, and atomically publish the V1.0 analytical star schema."""

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
from typing import Any, Iterable, Mapping
from uuid import uuid4

import numpy as np
import pandas as pd
import pyarrow

from src.config import ScenarioConfig


DIMENSION_TABLES = (
    "dim_customer",
    "dim_product",
    "dim_location",
    "dim_operational_site",
    "dim_vehicle",
    "dim_date",
)
FACT_TABLES = (
    "fact_orders",
    "fact_order_lines",
    "fact_deliveries",
    "fact_delivery_lines",
    "fact_inventory",
    "fact_cost_to_serve",
)
TECHNICAL_TABLES = ("meta_run", "qa_results")
MART_TABLES = DIMENSION_TABLES + FACT_TABLES + TECHNICAL_TABLES
VALIDATED_DATASETS = (
    "customers",
    "products",
    "locations",
    "operational_sites",
    "vehicles",
    "orders",
    "order_lines",
    "inventory",
    "deliveries",
    "delivery_lines",
    "cost_activities",
)

_CURRENCY_TOLERANCE = 0.01
_QUANTITY_TOLERANCE = 0.001
_RATIO_TOLERANCE = 1e-9
_MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
_DAY_NAMES = (
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
)


class MartsBuildError(RuntimeError):
    """Raised when approved validated inputs cannot safely feed the marts."""


@dataclass(frozen=True)
class MartGateResult:
    gate_id: str
    category: str
    severity: str
    tables: tuple[str, ...]
    rows_evaluated: int
    violation_count: int
    message: str

    @property
    def status(self) -> str:
        return "passed" if self.violation_count == 0 else "failed"

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "category": self.category,
            "severity": self.severity,
            "tables": list(self.tables),
            "rows_evaluated": self.rows_evaluated,
            "violation_count": self.violation_count,
            "violation_rate": (
                round(self.violation_count / self.rows_evaluated, 12)
                if self.rows_evaluated
                else (0.0 if self.violation_count == 0 else 1.0)
            ),
            "status": self.status,
            "message": self.message,
        }


@dataclass(frozen=True)
class MartsRun:
    marts_execution_id: str
    validation_execution_id: str
    dataset_build_id: str
    published: bool
    status: str
    results: tuple[MartGateResult, ...]
    controls: tuple[Mapping[str, Any], ...]
    mart_hashes: Mapping[str, str]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _combined_sha256(hashes: Mapping[str, str]) -> str:
    payload = "\n".join(f"{name}:{hashes[name]}" for name in sorted(hashes))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


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


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MartsBuildError(f"cannot read required evidence {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise MartsBuildError(f"required evidence {path.name} must be a JSON object")
    return payload


def _promote(staged: list[tuple[Path, Path]], token: str) -> None:
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
        for _, target in staged:
            if target.exists():
                backup = target.parent / f".{target.name}.backup-{token}"
                replace_with_retry(target, backup)
                backups[target] = backup
        for source, target in staged:
            replace_with_retry(source, target)
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
        for source, _ in staged:
            if source.exists():
                shutil.rmtree(source)
        for backup in backups.values():
            if backup.exists():
                shutil.rmtree(backup)


def _load_validated_inputs(
    config: ScenarioConfig,
    validated_dir: Path,
    manifest_dir: Path,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any], dict[str, Any]]:
    manifest = _read_json(manifest_dir / "run_manifest.json")
    quality = _read_json(manifest_dir / "quality_report.json")
    if manifest.get("status") != "passed" or quality.get("status") != "passed":
        raise MartsBuildError("validated input is not backed by passed QA evidence")
    if manifest.get("scenario_id") != config.scenario_id:
        raise MartsBuildError("validated scenario_id differs from configuration")
    if manifest.get("config_sha256") != config.config_sha256:
        raise MartsBuildError("validated config_sha256 differs from configuration")
    if manifest.get("dataset_build_id") != quality.get("dataset_build_id"):
        raise MartsBuildError("manifest and quality report identify different builds")
    if quality.get("summary", {}).get("failed_gates") != 0:
        raise MartsBuildError("quality report contains failed source gates")

    expected_hashes = manifest.get("artifacts", {}).get("validated_parquet_sha256", {})
    if set(expected_hashes) != set(VALIDATED_DATASETS):
        raise MartsBuildError("manifest does not enumerate all validated datasets")

    tables: dict[str, pd.DataFrame] = {}
    for name in VALIDATED_DATASETS:
        path = validated_dir / f"{name}.parquet"
        if not path.is_file():
            raise MartsBuildError(f"validated dataset is missing: {name}")
        if _sha256(path) != expected_hashes[name]:
            raise MartsBuildError(f"validated checksum mismatch: {name}")
        try:
            tables[name] = pd.read_parquet(path, engine="pyarrow")
        except Exception as exc:
            raise MartsBuildError(
                f"cannot read validated dataset {name}: {type(exc).__name__}"
            ) from exc
    return tables, manifest, quality


def _dimension(
    table: pd.DataFrame,
    business_key: str,
    surrogate_key: str,
    columns: Iterable[str],
) -> pd.DataFrame:
    result = table.loc[:, list(columns)].sort_values(business_key).reset_index(drop=True)
    result.insert(0, surrogate_key, pd.Series(range(1, len(result) + 1), dtype="int64"))
    return result


def _key_map(dimension: pd.DataFrame, business_key: str, surrogate_key: str) -> pd.Series:
    return dimension.set_index(business_key)[surrogate_key]


def _local_date(values: pd.Series, timezone_name: str) -> pd.Series:
    converted = pd.to_datetime(values, utc=True, errors="coerce")
    return converted.dt.tz_convert(timezone_name).dt.tz_localize(None).dt.normalize()


def _date_key(values: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(values, errors="coerce")
    keys = pd.to_numeric(parsed.dt.strftime("%Y%m%d"), errors="coerce")
    return keys.astype("Int64")


def _service_metrics(tables: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    orders = tables["orders"]
    order_lines = tables["order_lines"]
    detail = (
        tables["delivery_lines"][["delivery_id", "order_line_id", "delivered_quantity"]]
        .merge(
            tables["deliveries"][["delivery_id", "delivery_datetime"]],
            on="delivery_id",
            how="left",
            validate="many_to_one",
        )
        .merge(
            order_lines[["order_line_id", "order_id", "ordered_quantity"]],
            on="order_line_id",
            how="left",
            validate="many_to_one",
        )
        .sort_values(["order_line_id", "delivery_datetime", "delivery_id"])
    )
    detail["cumulative_delivered"] = detail.groupby("order_line_id")[
        "delivered_quantity"
    ].cumsum()
    completed = detail[detail["cumulative_delivered"].ge(detail["ordered_quantity"])]
    line_completion = completed.groupby("order_line_id")["delivery_datetime"].min()
    delivered_by_line = detail.groupby("order_line_id")["delivered_quantity"].sum()

    line_state = order_lines[["order_line_id", "order_id", "ordered_quantity"]].copy()
    line_state["delivered_quantity"] = line_state["order_line_id"].map(
        delivered_by_line
    ).fillna(0)
    line_state["line_full"] = line_state["delivered_quantity"].ge(
        line_state["ordered_quantity"]
    )
    line_state["line_completion"] = line_state["order_line_id"].map(line_completion)
    order_full = line_state.groupby("order_id")["line_full"].all()
    order_completion = line_state.groupby("order_id")["line_completion"].max()

    promise = orders.set_index("order_id")["promised_delivery_datetime"]
    detail["promise"] = detail["order_id"].map(promise)
    detail["positive_on_time"] = detail["delivery_datetime"].le(detail["promise"])
    any_on_time = detail.groupby("order_id")["positive_on_time"].any()

    service = orders[["order_id", "promised_delivery_datetime"]].copy()
    service["in_full_flag"] = service["order_id"].map(order_full).fillna(False)
    service["completion_datetime"] = service["order_id"].map(order_completion)
    service["any_delivery_on_time_flag"] = service["order_id"].map(any_on_time).fillna(False)
    service["service_class"] = "partial_late"
    service.loc[
        ~service["in_full_flag"] & service["any_delivery_on_time_flag"],
        "service_class",
    ] = "partial_on_time"
    service.loc[
        service["in_full_flag"]
        & service["completion_datetime"].gt(service["promised_delivery_datetime"]),
        "service_class",
    ] = "complete_late"
    service.loc[
        service["in_full_flag"]
        & service["completion_datetime"].le(service["promised_delivery_datetime"]),
        "service_class",
    ] = "complete_on_time"
    service["on_time_flag"] = (
        service["in_full_flag"]
        & service["completion_datetime"].le(service["promised_delivery_datetime"])
    )
    return service


def build_mart_tables(
    tables: Mapping[str, pd.DataFrame],
    config: ScenarioConfig,
    manifest: Mapping[str, Any],
    quality: Mapping[str, Any],
) -> dict[str, pd.DataFrame]:
    """Transform approved validated tables into deterministic conformed marts."""

    dim_customer = _dimension(
        tables["customers"], "customer_id", "customer_key",
        (
            "customer_id", "customer_name", "customer_segment", "location_id",
            "created_date", "is_active", "scenario_id", "dataset_build_id",
            "is_synthetic",
        ),
    )
    dim_product = _dimension(
        tables["products"], "sku_id", "product_key",
        (
            "sku_id", "sku_name", "product_family", "unit",
            "reference_list_unit_price", "reference_variable_unit_cost",
            "weight_kg", "volume_m3", "is_active", "scenario_id",
            "dataset_build_id", "is_synthetic",
        ),
    )
    dim_location = _dimension(
        tables["locations"], "location_id", "location_key",
        (
            "location_id", "location_type", "commune", "region", "country_code",
            "latitude", "longitude", "data_class", "scenario_id",
            "dataset_build_id", "is_synthetic",
        ),
    )
    dim_site = _dimension(
        tables["operational_sites"], "site_id", "site_key",
        (
            "site_id", "location_id", "site_type", "is_active", "scenario_id",
            "dataset_build_id", "is_synthetic",
        ),
    )
    dim_vehicle = _dimension(
        tables["vehicles"], "vehicle_id", "vehicle_key",
        (
            "vehicle_id", "vehicle_type", "capacity_kg", "capacity_m3",
            "fixed_cost_day", "variable_cost_km", "is_active", "scenario_id",
            "dataset_build_id", "is_synthetic",
        ),
    )
    not_applicable = pd.DataFrame(
        [{
            "vehicle_key": 0,
            "vehicle_id": "N/A",
            "vehicle_type": "Not applicable",
            "capacity_kg": pd.NA,
            "capacity_m3": pd.NA,
            "fixed_cost_day": pd.NA,
            "variable_cost_km": pd.NA,
            "is_active": False,
            "scenario_id": config.scenario_id,
            "dataset_build_id": manifest["dataset_build_id"],
            "is_synthetic": True,
        }]
    )
    dim_vehicle = pd.concat([not_applicable, dim_vehicle], ignore_index=True)

    customer_keys = _key_map(dim_customer, "customer_id", "customer_key")
    product_keys = _key_map(dim_product, "sku_id", "product_key")
    location_keys = _key_map(dim_location, "location_id", "location_key")
    site_keys = _key_map(dim_site, "site_id", "site_key")
    vehicle_keys = _key_map(dim_vehicle, "vehicle_id", "vehicle_key")
    customer_locations = tables["customers"].set_index("customer_id")["location_id"]

    orders = tables["orders"].copy()
    order_lines = tables["order_lines"].copy()
    deliveries = tables["deliveries"].copy()
    delivery_lines = tables["delivery_lines"].copy()
    costs = tables["cost_activities"].copy()

    order_lookup = orders.set_index("order_id")
    line_lookup = order_lines.set_index("order_line_id")
    delivery_lookup = deliveries.set_index("delivery_id")

    delivery_detail = delivery_lines.merge(
        order_lines[
            [
                "order_line_id", "order_id", "sku_id", "net_unit_price",
                "unit_variable_cost",
            ]
        ],
        on="order_line_id", how="left", validate="many_to_one",
    ).merge(
        deliveries[
            [
                "delivery_id", "vehicle_id", "origin_site_id",
                "destination_location_id", "delivery_datetime",
            ]
        ],
        on="delivery_id", how="left", validate="many_to_one",
    )
    delivery_detail["customer_id"] = delivery_detail["order_id"].map(
        order_lookup["customer_id"]
    )
    delivery_detail["order_datetime"] = delivery_detail["order_id"].map(
        order_lookup["order_datetime"]
    )
    delivery_detail["promised_delivery_datetime"] = delivery_detail["order_id"].map(
        order_lookup["promised_delivery_datetime"]
    )
    delivery_detail["recognized_net_sales"] = (
        delivery_detail["delivered_quantity"] * delivery_detail["net_unit_price"]
    ).round(2)
    delivery_detail["variable_product_cost"] = (
        delivery_detail["delivered_quantity"] * delivery_detail["unit_variable_cost"]
    ).round(2)
    delivery_detail["contribution_margin"] = (
        delivery_detail["recognized_net_sales"]
        - delivery_detail["variable_product_cost"]
    ).round(2)

    fact_delivery_lines = pd.DataFrame(
        {
            "delivery_line_id": delivery_detail["delivery_line_id"],
            "delivery_id": delivery_detail["delivery_id"],
            "order_line_id": delivery_detail["order_line_id"],
            "order_id": delivery_detail["order_id"],
            "customer_key": delivery_detail["customer_id"].map(customer_keys),
            "product_key": delivery_detail["sku_id"].map(product_keys),
            "location_key": delivery_detail["destination_location_id"].map(location_keys),
            "site_key": delivery_detail["origin_site_id"].map(site_keys),
            "vehicle_key": delivery_detail["vehicle_id"].map(vehicle_keys),
            "order_date_key": _date_key(
                _local_date(delivery_detail["order_datetime"], config.timezone)
            ),
            "delivery_date_key": _date_key(
                _local_date(delivery_detail["delivery_datetime"], config.timezone)
            ),
            "promised_date_key": _date_key(
                _local_date(delivery_detail["promised_delivery_datetime"], config.timezone)
            ),
            "delivered_quantity": delivery_detail["delivered_quantity"],
            "recognized_net_sales": delivery_detail["recognized_net_sales"],
            "variable_product_cost": delivery_detail["variable_product_cost"],
            "contribution_margin": delivery_detail["contribution_margin"],
            "scenario_id": delivery_detail["scenario_id"],
            "dataset_build_id": delivery_detail["dataset_build_id"],
            "is_synthetic": delivery_detail["is_synthetic"],
        }
    ).sort_values("delivery_line_id").reset_index(drop=True)

    product_weight = tables["products"].set_index("sku_id")["weight_kg"]
    product_volume = tables["products"].set_index("sku_id")["volume_m3"]
    delivery_detail["weight_kg"] = delivery_detail["sku_id"].map(product_weight)
    delivery_detail["volume_m3"] = delivery_detail["sku_id"].map(product_volume)
    delivery_detail["delivered_weight_kg"] = (
        delivery_detail["delivered_quantity"] * delivery_detail["weight_kg"]
    )
    delivery_detail["delivered_volume_m3"] = (
        delivery_detail["delivered_quantity"] * delivery_detail["volume_m3"]
    )
    delivery_loads = delivery_detail.groupby("delivery_id", as_index=True).agg(
        delivered_quantity=("delivered_quantity", "sum"),
        delivered_weight_kg=("delivered_weight_kg", "sum"),
        delivered_volume_m3=("delivered_volume_m3", "sum"),
    )
    delivery_base = deliveries.copy()
    delivery_base["customer_id"] = delivery_base["order_id"].map(order_lookup["customer_id"])
    delivery_base["order_datetime"] = delivery_base["order_id"].map(
        order_lookup["order_datetime"]
    )
    delivery_base["promised_delivery_datetime"] = delivery_base["order_id"].map(
        order_lookup["promised_delivery_datetime"]
    )
    for column in delivery_loads.columns:
        delivery_base[column] = delivery_base["delivery_id"].map(delivery_loads[column])
    vehicle_lookup = tables["vehicles"].set_index("vehicle_id")
    delivery_base["capacity_kg"] = delivery_base["vehicle_id"].map(
        vehicle_lookup["capacity_kg"]
    )
    delivery_base["capacity_m3"] = delivery_base["vehicle_id"].map(
        vehicle_lookup["capacity_m3"]
    )
    delivery_base["weight_utilization"] = (
        delivery_base["delivered_weight_kg"] / delivery_base["capacity_kg"]
    )
    delivery_base["volume_utilization"] = (
        delivery_base["delivered_volume_m3"] / delivery_base["capacity_m3"]
    )
    delivery_base["delivery_utilization"] = delivery_base[
        ["weight_utilization", "volume_utilization"]
    ].max(axis=1)
    fact_deliveries = pd.DataFrame(
        {
            "delivery_id": delivery_base["delivery_id"],
            "order_id": delivery_base["order_id"],
            "customer_key": delivery_base["customer_id"].map(customer_keys),
            "location_key": delivery_base["destination_location_id"].map(location_keys),
            "site_key": delivery_base["origin_site_id"].map(site_keys),
            "vehicle_key": delivery_base["vehicle_id"].map(vehicle_keys),
            "order_date_key": _date_key(
                _local_date(delivery_base["order_datetime"], config.timezone)
            ),
            "dispatch_date_key": _date_key(
                _local_date(delivery_base["dispatch_datetime"], config.timezone)
            ),
            "delivery_date_key": _date_key(
                _local_date(delivery_base["delivery_datetime"], config.timezone)
            ),
            "promised_date_key": _date_key(
                _local_date(delivery_base["promised_delivery_datetime"], config.timezone)
            ),
            "delivery_sequence": delivery_base["delivery_sequence"],
            "delivery_status": delivery_base["delivery_status"],
            "distance_km": delivery_base["distance_km"],
            "delivered_quantity": delivery_base["delivered_quantity"],
            "delivered_weight_kg": delivery_base["delivered_weight_kg"].round(3),
            "delivered_volume_m3": delivery_base["delivered_volume_m3"].round(6),
            "capacity_kg": delivery_base["capacity_kg"],
            "capacity_m3": delivery_base["capacity_m3"],
            "weight_utilization": delivery_base["weight_utilization"],
            "volume_utilization": delivery_base["volume_utilization"],
            "delivery_utilization": delivery_base["delivery_utilization"],
            "scenario_id": delivery_base["scenario_id"],
            "dataset_build_id": delivery_base["dataset_build_id"],
            "is_synthetic": delivery_base["is_synthetic"],
        }
    ).sort_values("delivery_id").reset_index(drop=True)

    delivered_by_line = delivery_lines.groupby("order_line_id")["delivered_quantity"].sum()
    line_base = order_lines.copy()
    line_base["customer_id"] = line_base["order_id"].map(order_lookup["customer_id"])
    line_base["location_id"] = line_base["customer_id"].map(customer_locations)
    line_base["order_datetime"] = line_base["order_id"].map(order_lookup["order_datetime"])
    line_base["promised_delivery_datetime"] = line_base["order_id"].map(
        order_lookup["promised_delivery_datetime"]
    )
    line_base["delivered_quantity"] = line_base["order_line_id"].map(
        delivered_by_line
    ).fillna(0)
    fact_order_lines = pd.DataFrame(
        {
            "order_line_id": line_base["order_line_id"],
            "order_id": line_base["order_id"],
            "customer_key": line_base["customer_id"].map(customer_keys),
            "product_key": line_base["sku_id"].map(product_keys),
            "location_key": line_base["location_id"].map(location_keys),
            "order_date_key": _date_key(
                _local_date(line_base["order_datetime"], config.timezone)
            ),
            "promised_date_key": _date_key(
                _local_date(line_base["promised_delivery_datetime"], config.timezone)
            ),
            "ordered_quantity": line_base["ordered_quantity"],
            "delivered_quantity": line_base["delivered_quantity"],
            "list_unit_price": line_base["list_unit_price"],
            "synthetic_discount_per_unit": line_base["synthetic_discount_per_unit"],
            "net_unit_price": line_base["net_unit_price"],
            "unit_variable_cost": line_base["unit_variable_cost"],
            "ordered_net_sales": line_base["ordered_net_sales"],
            "scenario_id": line_base["scenario_id"],
            "dataset_build_id": line_base["dataset_build_id"],
            "is_synthetic": line_base["is_synthetic"],
        }
    ).sort_values("order_line_id").reset_index(drop=True)

    cost_base = costs.copy()
    cost_base["customer_id"] = cost_base["order_id"].map(order_lookup["customer_id"])
    cost_base["location_id"] = cost_base["customer_id"].map(customer_locations)
    cost_base["order_datetime"] = cost_base["order_id"].map(order_lookup["order_datetime"])
    cost_base["vehicle_id"] = cost_base["delivery_id"].map(delivery_lookup["vehicle_id"])
    cost_base["delivery_datetime"] = cost_base["delivery_id"].map(
        delivery_lookup["delivery_datetime"]
    )
    fact_costs = pd.DataFrame(
        {
            "cost_activity_id": cost_base["cost_activity_id"],
            "order_id": cost_base["order_id"],
            "delivery_id": cost_base["delivery_id"],
            "customer_key": cost_base["customer_id"].map(customer_keys),
            "location_key": cost_base["location_id"].map(location_keys),
            "vehicle_key": cost_base["vehicle_id"].map(vehicle_keys).fillna(0).astype("int64"),
            "order_date_key": _date_key(
                _local_date(cost_base["order_datetime"], config.timezone)
            ),
            "activity_date_key": _date_key(
                _local_date(cost_base["activity_datetime"], config.timezone)
            ),
            "delivery_date_key": _date_key(
                _local_date(cost_base["delivery_datetime"], config.timezone)
            ),
            "cost_type": cost_base["cost_type"],
            "cost_amount": cost_base["cost_amount"],
            "currency_code": cost_base["currency_code"],
            "cost_driver_value": cost_base["cost_driver_value"],
            "cost_driver_unit": cost_base["cost_driver_unit"],
            "allocation_method": cost_base["allocation_method"],
            "scenario_id": cost_base["scenario_id"],
            "dataset_build_id": cost_base["dataset_build_id"],
            "is_synthetic": cost_base["is_synthetic"],
        }
    ).sort_values("cost_activity_id").reset_index(drop=True)

    line_totals = fact_order_lines.groupby("order_id").agg(
        ordered_quantity=("ordered_quantity", "sum"),
        delivered_quantity=("delivered_quantity", "sum"),
    )
    economics = fact_delivery_lines.groupby("order_id").agg(
        recognized_net_sales=("recognized_net_sales", "sum"),
        variable_product_cost=("variable_product_cost", "sum"),
        contribution_margin=("contribution_margin", "sum"),
    )
    cts = fact_costs.groupby("order_id")["cost_amount"].sum()
    service = _service_metrics(tables).set_index("order_id")
    order_base = orders.copy()
    order_base["location_id"] = order_base["customer_id"].map(customer_locations)
    for column in line_totals.columns:
        order_base[column] = order_base["order_id"].map(line_totals[column]).fillna(0)
    for column in economics.columns:
        order_base[column] = order_base["order_id"].map(economics[column]).fillna(0)
    order_base["cts_amount"] = order_base["order_id"].map(cts).fillna(0)
    order_base["mc_cts_amount"] = (
        order_base["contribution_margin"] - order_base["cts_amount"]
    ).round(2)
    for column in (
        "in_full_flag", "completion_datetime", "any_delivery_on_time_flag",
        "service_class", "on_time_flag",
    ):
        order_base[column] = order_base["order_id"].map(service[column])
    promised_dates = _local_date(order_base["promised_delivery_datetime"], config.timezone)
    order_base["eligible_order_flag"] = promised_dates.between(
        pd.Timestamp(config.period_start), pd.Timestamp(config.period_end), inclusive="both"
    )
    order_base["order_otif_flag"] = (
        order_base["eligible_order_flag"]
        & order_base["in_full_flag"]
        & order_base["on_time_flag"]
    )
    order_base["lead_time_hours"] = (
        (order_base["completion_datetime"] - order_base["order_datetime"])
        .dt.total_seconds()
        .div(3600)
        .where(order_base["in_full_flag"])
    )
    fact_orders = pd.DataFrame(
        {
            "order_id": order_base["order_id"],
            "customer_key": order_base["customer_id"].map(customer_keys),
            "location_key": order_base["location_id"].map(location_keys),
            "order_date_key": _date_key(
                _local_date(order_base["order_datetime"], config.timezone)
            ),
            "promised_date_key": _date_key(promised_dates),
            "completion_date_key": _date_key(
                _local_date(order_base["completion_datetime"], config.timezone)
            ),
            "order_status": order_base["order_status"],
            "eligible_order_flag": order_base["eligible_order_flag"],
            "in_full_flag": order_base["in_full_flag"],
            "on_time_flag": order_base["on_time_flag"],
            "order_otif_flag": order_base["order_otif_flag"],
            "any_delivery_on_time_flag": order_base["any_delivery_on_time_flag"],
            "service_class": order_base["service_class"],
            "ordered_quantity": order_base["ordered_quantity"],
            "delivered_quantity": order_base["delivered_quantity"],
            "lead_time_hours": order_base["lead_time_hours"],
            "recognized_net_sales": order_base["recognized_net_sales"].round(2),
            "variable_product_cost": order_base["variable_product_cost"].round(2),
            "contribution_margin": order_base["contribution_margin"].round(2),
            "cts_amount": order_base["cts_amount"].round(2),
            "mc_cts_amount": order_base["mc_cts_amount"],
            "scenario_id": order_base["scenario_id"],
            "dataset_build_id": order_base["dataset_build_id"],
            "is_synthetic": order_base["is_synthetic"],
        }
    ).sort_values("order_id").reset_index(drop=True)

    inventory = tables["inventory"].copy()
    fact_inventory = pd.DataFrame(
        {
            "snapshot_date_key": _date_key(inventory["snapshot_date"]),
            "site_key": inventory["site_id"].map(site_keys),
            "product_key": inventory["sku_id"].map(product_keys),
            "on_hand_quantity": inventory["on_hand_quantity"],
            "allocated_quantity": inventory["allocated_quantity"],
            "available_quantity": inventory["available_quantity"],
            "safety_stock_quantity": inventory["safety_stock_quantity"],
            "reorder_point_quantity": inventory["reorder_point_quantity"],
            "is_stockout": inventory["is_stockout"],
            "is_low_inventory": inventory["is_low_inventory"],
            "scenario_id": inventory["scenario_id"],
            "dataset_build_id": inventory["dataset_build_id"],
            "is_synthetic": inventory["is_synthetic"],
        }
    ).sort_values(["snapshot_date_key", "site_key", "product_key"]).reset_index(drop=True)

    date_values: list[pd.Series] = [
        pd.Series([pd.Timestamp(config.period_start), pd.Timestamp(config.period_end)])
    ]
    for frame, columns in (
        (fact_orders, ("order_date_key", "promised_date_key", "completion_date_key")),
        (fact_order_lines, ("order_date_key", "promised_date_key")),
        (fact_deliveries, ("order_date_key", "dispatch_date_key", "delivery_date_key", "promised_date_key")),
        (fact_delivery_lines, ("order_date_key", "delivery_date_key", "promised_date_key")),
        (fact_inventory, ("snapshot_date_key",)),
        (fact_costs, ("order_date_key", "activity_date_key", "delivery_date_key")),
    ):
        for column in columns:
            values = pd.to_datetime(frame[column].astype("string"), format="%Y%m%d", errors="coerce")
            date_values.append(values.dropna())
    all_dates = pd.concat(date_values, ignore_index=True).dropna()
    calendar = pd.date_range(all_dates.min(), all_dates.max(), freq="D")
    dim_date = pd.DataFrame({"date": calendar})
    dim_date.insert(0, "date_key", calendar.strftime("%Y%m%d").astype("int64"))
    dim_date["year"] = calendar.year
    dim_date["quarter"] = "Q" + calendar.quarter.astype(str)
    dim_date["month_number"] = calendar.month
    dim_date["month_name"] = [
        _MONTH_NAMES[month - 1] for month in calendar.month
    ]
    dim_date["year_month"] = calendar.strftime("%Y-%m")
    dim_date["month_start"] = calendar.to_period("M").to_timestamp()
    dim_date["day_of_month"] = calendar.day
    dim_date["day_of_week_number"] = calendar.dayofweek + 1
    dim_date["day_name"] = [_DAY_NAMES[day] for day in calendar.dayofweek]
    dim_date["is_weekend"] = calendar.dayofweek >= 5

    source_hashes = manifest["artifacts"]["validated_parquet_sha256"]
    meta_run = pd.DataFrame(
        [{
            "scenario_id": config.scenario_id,
            "dataset_build_id": manifest["dataset_build_id"],
            "validation_execution_id": manifest["execution_id"],
            "validated_at": manifest["executed_at"],
            "period_start": config.period_start,
            "period_end": config.period_end,
            "max_order_date": pd.to_datetime(
                fact_orders["order_date_key"].astype("string"),
                format="%Y%m%d",
            ).max().date(),
            "max_available_date": pd.to_datetime(dim_date["date"].max()).date(),
            "config_sha256": manifest["config_sha256"],
            "schema_version": manifest["schema_version"],
            "validated_combined_sha256": _combined_sha256(source_hashes),
            "source_quality_status": quality["status"],
            "source_quality_passed_gates": quality["summary"]["passed_gates"],
            "source_quality_total_gates": quality["summary"]["total_gates"],
            "is_synthetic": True,
        }]
    )

    return {
        "dim_customer": dim_customer,
        "dim_product": dim_product,
        "dim_location": dim_location,
        "dim_operational_site": dim_site,
        "dim_vehicle": dim_vehicle,
        "dim_date": dim_date,
        "fact_orders": fact_orders,
        "fact_order_lines": fact_order_lines,
        "fact_deliveries": fact_deliveries,
        "fact_delivery_lines": fact_delivery_lines,
        "fact_inventory": fact_inventory,
        "fact_cost_to_serve": fact_costs,
        "meta_run": meta_run,
    }


def _divide(numerator: float, denominator: float) -> float | None:
    return None if denominator == 0 else numerator / denominator


def calculate_kpi_controls(marts: Mapping[str, pd.DataFrame]) -> tuple[dict[str, Any], ...]:
    orders = marts["fact_orders"]
    lines = marts["fact_order_lines"]
    deliveries = marts["fact_deliveries"]
    inventory = marts["fact_inventory"]
    costs = marts["fact_cost_to_serve"]
    net_sales = float(orders["recognized_net_sales"].sum())
    variable_cost = float(orders["variable_product_cost"].sum())
    contribution = net_sales - variable_cost
    cts = float(orders["cts_amount"].sum())
    order_count = int(orders["order_id"].nunique())
    eligible = int(orders["eligible_order_flag"].sum())
    otif_orders = int((orders["eligible_order_flag"] & orders["order_otif_flag"]).sum())
    ordered_quantity = float(lines["ordered_quantity"].sum())
    delivered_quantity = float(lines["delivered_quantity"].sum())
    complete_lead = orders.loc[orders["in_full_flag"], "lead_time_hours"]
    inventory_observations = len(inventory)
    stockouts = int(inventory["is_stockout"].sum())
    last_date = inventory["snapshot_date_key"].max()
    eop = float(
        inventory.loc[inventory["snapshot_date_key"].eq(last_date), "available_quantity"].sum()
    )
    customers = int(orders["customer_key"].nunique())
    distance = float(deliveries["distance_km"].sum())
    transport_cost = float(costs.loc[costs["cost_type"].eq("transport"), "cost_amount"].sum())
    utilization = float(deliveries["delivery_utilization"].mean())

    specs = (
        ("KPI-01", "Net Sales", net_sales, None, None, "fact_orders", "order_date_key", "CLP 0.00", "order, customer, location, period"),
        ("KPI-02", "Variable Product Cost", variable_cost, None, None, "fact_orders", "order_date_key", "CLP 0.00", "order, customer, location, period"),
        ("KPI-03", "Contribution Margin", contribution, net_sales, variable_cost, "fact_orders", "order_date_key", "CLP 0.00", "order, customer, location, period"),
        ("KPI-04", "CTS", cts, None, None, "fact_orders", "order_date_key", "CLP 0.00", "order, customer, location, period"),
        ("KPI-05", "MC_CTS", contribution - cts, contribution, cts, "fact_orders", "order_date_key", "CLP 0.00", "order, customer, location, period; not SKU"),
        ("KPI-06", "Orders", order_count, None, None, "fact_orders", "order_date_key", "0", "customer, location, period"),
        ("KPI-07", "Average Order Value", _divide(net_sales, order_count), net_sales, order_count, "fact_orders", "order_date_key", "CLP 0.00", "customer, location, period"),
        ("KPI-08", "OTIF", _divide(otif_orders, eligible), otif_orders, eligible, "fact_orders", "promised_date_key", "0.0%", "order, customer, location, period"),
        ("KPI-09", "Fill Rate", _divide(delivered_quantity, ordered_quantity), delivered_quantity, ordered_quantity, "fact_order_lines", "promised_date_key", "0.0%", "SKU, customer, location, period"),
        ("KPI-10", "Order-to-Delivery Lead Time", float(complete_lead.mean()) if len(complete_lead) else None, float(complete_lead.sum()) if len(complete_lead) else None, len(complete_lead), "fact_orders", "promised_date_key", "0.00 hours", "customer, location, period"),
        ("KPI-11", "Stockout Rate", _divide(stockouts, inventory_observations), stockouts, inventory_observations, "fact_inventory", "snapshot_date_key", "0.0%", "SKU, site, period"),
        ("KPI-12", "Available Inventory EOP", eop, eop, None, "fact_inventory", "snapshot_date_key", "0.000 units", "SKU, site, closing date"),
        ("KPI-13", "Customer Frequency", _divide(order_count, customers), order_count, customers, "fact_orders", "order_date_key", "0.00", "segment, location, period"),
        ("KPI-14", "Delivery Distance", distance, None, None, "fact_deliveries", "delivery_date_key", "0.000 km", "vehicle, customer, location, period"),
        ("KPI-15", "Transport Cost", transport_cost, None, None, "fact_cost_to_serve", "order_date_key", "CLP 0.00", "order, customer, location, period"),
        ("KPI-16", "Vehicle Utilization", utilization, float(deliveries["delivery_utilization"].sum()), len(deliveries), "fact_deliveries", "delivery_date_key", "0.0%", "vehicle, period"),
        ("KPI-17", "Customers", customers, None, None, "fact_orders", "order_date_key", "0", "segment, location, period"),
    )
    return tuple(
        {
            "kpi_id": kpi_id,
            "measure_name": name,
            "python_control_value": value,
            "numerator": numerator,
            "denominator": denominator,
            "source_fact": source,
            "date_role": date_role,
            "valid_grain": valid_grain,
            "format": display_format,
            "status": "computed" if value is not None else "blank_zero_denominator",
        }
        for (
            kpi_id, name, value, numerator, denominator, source, date_role,
            display_format, valid_grain,
        ) in specs
    )


def _gate(
    results: list[MartGateResult], gate_id: str, category: str, tables: Iterable[str],
    rows: int, violations: int, message: str, severity: str = "critical",
) -> None:
    results.append(
        MartGateResult(
            gate_id, category, severity, tuple(tables), int(rows), int(violations), message
        )
    )


def _not_close(actual: float, expected: float, tolerance: float) -> int:
    return int(not np.isclose(actual, expected, rtol=0.0, atol=tolerance))


def validate_mart_tables(
    marts: Mapping[str, pd.DataFrame],
    validated: Mapping[str, pd.DataFrame],
    manifest: Mapping[str, Any],
) -> tuple[MartGateResult, ...]:
    """Validate grains, conformed keys, date roles, and reconciled measures."""

    results: list[MartGateResult] = []
    dimension_keys = {
        "dim_customer": ("customer_key", "customer_id"),
        "dim_product": ("product_key", "sku_id"),
        "dim_location": ("location_key", "location_id"),
        "dim_operational_site": ("site_key", "site_id"),
        "dim_vehicle": ("vehicle_key", "vehicle_id"),
        "dim_date": ("date_key", "date"),
    }
    for name, (surrogate, business) in dimension_keys.items():
        table = marts[name]
        violations = int(table[surrogate].isna().sum() + table[surrogate].duplicated().sum())
        _gate(results, f"dimension.{name}.surrogate_key", "dimension_key", (name,), len(table), violations, "surrogate key is populated and unique")
        violations = int(table[business].isna().sum() + table[business].duplicated().sum())
        _gate(results, f"dimension.{name}.business_key", "dimension_key", (name,), len(table), violations, "business key is populated and unique")

    fact_grains = {
        "fact_orders": ("order_id",),
        "fact_order_lines": ("order_line_id",),
        "fact_deliveries": ("delivery_id",),
        "fact_delivery_lines": ("delivery_id", "order_line_id"),
        "fact_inventory": ("snapshot_date_key", "site_key", "product_key"),
        "fact_cost_to_serve": ("cost_activity_id",),
    }
    for name, grain in fact_grains.items():
        table = marts[name]
        violations = int(table[list(grain)].isna().any(axis=1).sum() + table.duplicated(list(grain)).sum())
        _gate(results, f"grain.{name}", "grain", (name,), len(table), violations, "declared fact grain is populated and unique")

    expected_rows = {
        "fact_orders": len(validated["orders"]),
        "fact_order_lines": len(validated["order_lines"]),
        "fact_deliveries": len(validated["deliveries"]),
        "fact_delivery_lines": len(validated["delivery_lines"]),
        "fact_inventory": len(validated["inventory"]),
        "fact_cost_to_serve": len(validated["cost_activities"]),
    }
    for name, expected in expected_rows.items():
        _gate(results, f"cardinality.{name}", "cardinality", (name,), expected, int(len(marts[name]) != expected), "fact row count matches its validated source grain")

    fk_rules = {
        "fact_orders": {"customer_key": "dim_customer", "location_key": "dim_location", "order_date_key": "dim_date", "promised_date_key": "dim_date", "completion_date_key": "dim_date"},
        "fact_order_lines": {"customer_key": "dim_customer", "product_key": "dim_product", "location_key": "dim_location", "order_date_key": "dim_date", "promised_date_key": "dim_date"},
        "fact_deliveries": {"customer_key": "dim_customer", "location_key": "dim_location", "site_key": "dim_operational_site", "vehicle_key": "dim_vehicle", "order_date_key": "dim_date", "dispatch_date_key": "dim_date", "delivery_date_key": "dim_date", "promised_date_key": "dim_date"},
        "fact_delivery_lines": {"customer_key": "dim_customer", "product_key": "dim_product", "location_key": "dim_location", "site_key": "dim_operational_site", "vehicle_key": "dim_vehicle", "order_date_key": "dim_date", "delivery_date_key": "dim_date", "promised_date_key": "dim_date"},
        "fact_inventory": {"site_key": "dim_operational_site", "product_key": "dim_product", "snapshot_date_key": "dim_date"},
        "fact_cost_to_serve": {"customer_key": "dim_customer", "location_key": "dim_location", "vehicle_key": "dim_vehicle", "order_date_key": "dim_date", "activity_date_key": "dim_date", "delivery_date_key": "dim_date"},
    }
    for fact_name, rules in fk_rules.items():
        fact = marts[fact_name]
        for column, dimension_name in rules.items():
            dimension_key = dimension_keys[dimension_name][0]
            allowed = set(marts[dimension_name][dimension_key].dropna())
            values = fact[column]
            violations = int((values.notna() & ~values.isin(allowed)).sum())
            _gate(results, f"relationship.{fact_name}.{column}", "relationship", (fact_name, dimension_name), len(fact), violations, "fact key resolves to exactly one conformed dimension row")

    orders = marts["fact_orders"]
    lines = marts["fact_order_lines"]
    delivery_lines = marts["fact_delivery_lines"]
    costs = marts["fact_cost_to_serve"]
    order_line_quantities = lines.groupby("order_id")[["ordered_quantity", "delivered_quantity"]].sum()
    for column in ("ordered_quantity", "delivered_quantity"):
        comparison = orders.set_index("order_id")[column].sub(order_line_quantities[column]).abs()
        _gate(results, f"reconcile.orders.{column}", "reconciliation", ("fact_orders", "fact_order_lines"), len(orders), int(comparison.gt(_QUANTITY_TOLERANCE).sum()), f"{column} reconciles from lines to orders")

    economic_columns = ("recognized_net_sales", "variable_product_cost", "contribution_margin")
    order_economics = delivery_lines.groupby("order_id")[list(economic_columns)].sum()
    for column in economic_columns:
        comparison = orders.set_index("order_id")[column].sub(order_economics[column]).abs()
        _gate(results, f"reconcile.orders.{column}", "reconciliation", ("fact_orders", "fact_delivery_lines"), len(orders), int(comparison.gt(_CURRENCY_TOLERANCE).sum()), f"{column} reconciles from delivery detail to orders")
    order_cts = costs.groupby("order_id")["cost_amount"].sum()
    comparison = orders.set_index("order_id")["cts_amount"].sub(order_cts).abs()
    _gate(results, "reconcile.orders.cts_amount", "reconciliation", ("fact_orders", "fact_cost_to_serve"), len(orders), int(comparison.gt(_CURRENCY_TOLERANCE).sum()), "CTS reconciles from unique cost activities to orders")
    mc_formula = (orders["recognized_net_sales"] - orders["variable_product_cost"] - orders["cts_amount"])
    _gate(results, "formula.orders.mc_cts", "formula", ("fact_orders",), len(orders), int(orders["mc_cts_amount"].sub(mc_formula).abs().gt(_CURRENCY_TOLERANCE).sum()), "MC_CTS equals Net Sales minus Variable Product Cost minus CTS")
    _gate(results, "formula.order_lines.no_overdelivery", "formula", ("fact_order_lines",), len(lines), int(lines["delivered_quantity"].gt(lines["ordered_quantity"] + _QUANTITY_TOLERANCE).sum()), "cumulative delivered quantity does not exceed ordered quantity")

    controls = {item["kpi_id"]: item for item in calculate_kpi_controls(marts)}
    validation_controls = manifest["control_metrics"]["control_totals"]
    comparisons = {
        "KPI-01": (validation_controls["recognized_net_sales"], _CURRENCY_TOLERANCE),
        "KPI-02": (validation_controls["variable_product_cost"], _CURRENCY_TOLERANCE),
        "KPI-03": (validation_controls["contribution_margin"], _CURRENCY_TOLERANCE),
        "KPI-04": (validation_controls["cost_to_serve"], _CURRENCY_TOLERANCE),
        "KPI-05": (validation_controls["mc_cts"], _CURRENCY_TOLERANCE),
        "KPI-08": (manifest["control_metrics"]["service_class_shares"]["complete_on_time"], _RATIO_TOLERANCE),
        "KPI-11": (manifest["control_metrics"]["stockout_rate"], 0.5e-6),
    }
    for kpi_id, (expected, tolerance) in comparisons.items():
        actual = controls[kpi_id]["python_control_value"]
        violations = 1 if actual is None else _not_close(float(actual), float(expected), tolerance)
        _gate(results, f"kpi.{kpi_id}.source_reconciliation", "kpi", (controls[kpi_id]["source_fact"],), 1, violations, "Python KPI control reconciles with validated source evidence")
    for kpi_id, control in controls.items():
        value = control["python_control_value"]
        violations = int(value is not None and isinstance(value, float) and not np.isfinite(value))
        _gate(results, f"kpi.{kpi_id}.finite", "kpi", (control["source_fact"],), 1, violations, "KPI is finite or BLANK for a zero denominator", severity="high")
    return tuple(results)


def _qa_results_table(
    source_quality: Mapping[str, Any],
    mart_results: tuple[MartGateResult, ...],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for result in source_quality["results"]:
        row = dict(result)
        row["stage"] = "validated_source"
        row["tables"] = json.dumps(row.pop("datasets"), separators=(",", ":"))
        rows.append(row)
    for result in mart_results:
        row = result.as_dict()
        row["stage"] = "analytical_marts"
        row["tables"] = json.dumps(row["tables"], separators=(",", ":"))
        rows.append(row)
    columns = (
        "stage", "gate_id", "category", "severity", "tables", "status",
        "rows_evaluated", "violation_count", "violation_rate", "message",
    )
    return pd.DataFrame(rows, columns=columns).sort_values(["stage", "gate_id"]).reset_index(drop=True)


def build_and_publish_marts(
    config: ScenarioConfig,
    validated_dir: str | Path,
    marts_dir: str | Path,
    manifest_dir: str | Path,
) -> MartsRun:
    """Build marts from passed Parquet inputs and atomically publish on full QA success."""

    started = perf_counter()
    marts_execution_id = "MRT-" + uuid4().hex.upper()
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    validated_path = Path(validated_dir).resolve()
    marts_path = Path(marts_dir).resolve()
    manifest_path = Path(manifest_dir).resolve()
    validated, manifest, quality = _load_validated_inputs(
        config, validated_path, manifest_path
    )
    marts = build_mart_tables(validated, config, manifest, quality)
    results = validate_mart_tables(marts, validated, manifest)
    controls = calculate_kpi_controls(marts)
    status = "passed" if all(result.status == "passed" for result in results) else "failed"
    report_payload = {
        "report_version": "1.0",
        "marts_execution_id": marts_execution_id,
        "validation_execution_id": manifest["execution_id"],
        "generated_at": generated_at,
        "scenario_id": config.scenario_id,
        "dataset_build_id": manifest["dataset_build_id"],
        "status": status,
        "summary": {
            "total_gates": len(results),
            "passed_gates": sum(result.status == "passed" for result in results),
            "failed_gates": sum(result.status == "failed" for result in results),
        },
        "results": [result.as_dict() for result in results],
    }

    if status != "passed":
        failure_dir = manifest_path / "marts_failures"
        failure_dir.mkdir(parents=True, exist_ok=True)
        temporary = failure_dir / f".{marts_execution_id}.tmp"
        final = failure_dir / f"{marts_execution_id}.json"
        _write_json(temporary, report_payload)
        os.replace(temporary, final)
        return MartsRun(
            marts_execution_id, manifest["execution_id"], manifest["dataset_build_id"],
            False, status, results, controls, {},
        )

    marts["qa_results"] = _qa_results_table(quality, results)
    token = uuid4().hex
    marts_path.parent.mkdir(parents=True, exist_ok=True)
    staged_marts = marts_path.parent / f".{marts_path.name}.staging-{token}"
    staged_manifest = manifest_path.parent / f".{manifest_path.name}.staging-{token}"
    staged_marts.mkdir(parents=False, exist_ok=False)
    shutil.copytree(manifest_path, staged_manifest)
    mart_hashes: dict[str, str] = {}
    try:
        for name in MART_TABLES:
            path = staged_marts / f"{name}.parquet"
            marts[name].to_parquet(
                path, index=False, engine="pyarrow", compression="snappy"
            )
            mart_hashes[name] = _sha256(path)

        _write_json(staged_manifest / "marts_quality_report.json", report_payload)
        controls_payload = {
            "control_version": "1.0",
            "scenario_id": config.scenario_id,
            "dataset_build_id": manifest["dataset_build_id"],
            "validation_execution_id": manifest["execution_id"],
            "controls": list(controls),
        }
        _write_json(staged_manifest / "kpi_controls.json", controls_payload)
        updated_manifest = dict(manifest)
        updated_manifest["paths"] = dict(manifest["paths"])
        updated_manifest["paths"]["marts_output"] = _display_path(marts_path)
        updated_manifest["artifacts"] = dict(manifest["artifacts"])
        updated_manifest["artifacts"]["marts_parquet_sha256"] = mart_hashes
        updated_manifest["artifacts"]["marts_combined_sha256"] = _combined_sha256(mart_hashes)
        deterministic_mart_hashes = {
            name: hash_value
            for name, hash_value in mart_hashes.items()
            if name != "meta_run"
        }
        updated_manifest["artifacts"][
            "marts_deterministic_combined_sha256"
        ] = _combined_sha256(deterministic_mart_hashes)
        updated_manifest["artifacts"]["marts_quality_report_sha256"] = _sha256(
            staged_manifest / "marts_quality_report.json"
        )
        updated_manifest["artifacts"]["kpi_controls_sha256"] = _sha256(
            staged_manifest / "kpi_controls.json"
        )
        updated_manifest["marts_build"] = {
            "execution_id": marts_execution_id,
            "built_at": generated_at,
            "duration_seconds": round(perf_counter() - started, 6),
            "status": "passed",
            "tables": {name: len(marts[name]) for name in MART_TABLES},
            "runtime_versions": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "pandas": pd.__version__,
                "pyarrow": pyarrow.__version__,
            },
        }
        updated_manifest["marts_quality_summary"] = report_payload["summary"]
        _write_json(staged_manifest / "run_manifest.json", updated_manifest)
        _promote([(staged_marts, marts_path), (staged_manifest, manifest_path)], token)
    except Exception:
        if staged_marts.exists():
            shutil.rmtree(staged_marts)
        if staged_manifest.exists():
            shutil.rmtree(staged_manifest)
        raise

    return MartsRun(
        marts_execution_id, manifest["execution_id"], manifest["dataset_build_id"],
        True, status, results, controls, mart_hashes,
    )
