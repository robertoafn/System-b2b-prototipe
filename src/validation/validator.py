"""Contract quality gates for V1.0 Core source datasets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.config import ScenarioConfig
from src.validation.schema import DataContractSchema, LoadedSource


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    category: str
    severity: str
    status: str
    datasets: tuple[str, ...]
    rows_evaluated: int
    violation_count: int
    violation_rate: float
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "category": self.category,
            "severity": self.severity,
            "status": self.status,
            "datasets": list(self.datasets),
            "rows_evaluated": self.rows_evaluated,
            "violation_count": self.violation_count,
            "violation_rate": self.violation_rate,
            "message": self.message,
        }


@dataclass(frozen=True)
class ValidationOutcome:
    status: str
    schema_version: str
    dataset_build_id: str | None
    tables: Mapping[str, pd.DataFrame]
    results: tuple[GateResult, ...]
    metrics: Mapping[str, Any]

    @property
    def passed(self) -> bool:
        return self.status == "passed"


class _Collector:
    def __init__(self) -> None:
        self.results: list[GateResult] = []

    def add(
        self,
        gate_id: str,
        category: str,
        severity: str,
        datasets: tuple[str, ...],
        rows_evaluated: int,
        violation_count: int,
        message: str,
    ) -> None:
        denominator = max(int(rows_evaluated), 0)
        violations = max(int(violation_count), 0)
        rate = violations / denominator if denominator else (1.0 if violations else 0.0)
        self.results.append(
            GateResult(
                gate_id=gate_id,
                category=category,
                severity=severity,
                status="failed" if violations else "passed",
                datasets=datasets,
                rows_evaluated=denominator,
                violation_count=violations,
                violation_rate=round(rate, 12),
                message=message,
            )
        )

    def mask(
        self,
        gate_id: str,
        category: str,
        severity: str,
        datasets: tuple[str, ...],
        invalid: pd.Series,
        message: str,
    ) -> None:
        normalized = invalid.astype("boolean").fillna(True)
        self.add(
            gate_id,
            category,
            severity,
            datasets,
            len(normalized),
            int(normalized.sum()),
            message,
        )


def _close(left: pd.Series, right: pd.Series, tolerance: float) -> pd.Series:
    return left.sub(right).abs().le(tolerance)


def _schema_gates(
    collector: _Collector,
    loaded: LoadedSource,
    schema: DataContractSchema,
) -> None:
    for dataset_name in schema.datasets:
        relevant = [
            finding for finding in loaded.findings if finding.dataset == dataset_name
        ]
        collector.add(
            f"schema.{dataset_name}",
            "schema",
            "critical",
            (dataset_name,),
            len(loaded.tables[dataset_name]),
            sum(finding.violation_count for finding in relevant),
            "; ".join(finding.message for finding in relevant)
            if relevant
            else "columns, required values, formats and logical types conform",
        )
    unexpected = [
        finding for finding in loaded.findings if finding.code == "unexpected_dataset"
    ]
    collector.add(
        "schema.dataset_set",
        "schema",
        "critical",
        tuple(sorted(schema.datasets)),
        len(schema.datasets),
        sum(finding.violation_count for finding in unexpected),
        "source directory contains only the eleven contracted datasets",
    )


def _identity_and_key_gates(
    collector: _Collector,
    tables: Mapping[str, pd.DataFrame],
    schema: DataContractSchema,
    config: ScenarioConfig,
) -> str | None:
    observed_build_ids: set[str] = set()
    identity_violations = 0
    rows = 0
    for table in tables.values():
        rows += len(table)
        identity_violations += int(table["scenario_id"].ne(config.scenario_id).fillna(True).sum())
        observed_build_ids.update(str(value) for value in table["dataset_build_id"].dropna().unique())
    if len(observed_build_ids) != 1:
        identity_violations += abs(len(observed_build_ids) - 1) or 1
    collector.add(
        "lineage.identity",
        "integrity",
        "critical",
        tuple(sorted(tables)),
        rows,
        identity_violations,
        "scenario_id and dataset_build_id are consistent across every dataset",
    )
    collector.add(
        "lineage.schema_version",
        "integrity",
        "critical",
        tuple(sorted(tables)),
        1,
        int(schema.schema_version != config.schema_version),
        "loaded schema version matches scenario configuration",
    )

    for name, dataset in schema.datasets.items():
        table = tables[name]
        null_pk = table.loc[:, dataset.primary_key].isna().any(axis=1)
        duplicate_pk = table.duplicated(list(dataset.primary_key), keep=False)
        collector.mask(
            f"pk.{name}",
            "uniqueness",
            "critical",
            (name,),
            null_pk | duplicate_pk,
            "primary key is non-null and unique at the declared grain",
        )

    return next(iter(observed_build_ids)) if len(observed_build_ids) == 1 else None


def _foreign_key_gates(
    collector: _Collector,
    tables: Mapping[str, pd.DataFrame],
) -> None:
    relations = (
        ("customers", "location_id", "locations", "location_id", False),
        ("operational_sites", "location_id", "locations", "location_id", False),
        ("orders", "customer_id", "customers", "customer_id", False),
        ("order_lines", "order_id", "orders", "order_id", False),
        ("order_lines", "sku_id", "products", "sku_id", False),
        ("inventory", "site_id", "operational_sites", "site_id", False),
        ("inventory", "sku_id", "products", "sku_id", False),
        ("deliveries", "order_id", "orders", "order_id", False),
        ("deliveries", "vehicle_id", "vehicles", "vehicle_id", False),
        ("deliveries", "origin_site_id", "operational_sites", "site_id", False),
        ("deliveries", "destination_location_id", "locations", "location_id", False),
        ("delivery_lines", "delivery_id", "deliveries", "delivery_id", False),
        ("delivery_lines", "order_line_id", "order_lines", "order_line_id", False),
        ("cost_activities", "order_id", "orders", "order_id", False),
        ("cost_activities", "delivery_id", "deliveries", "delivery_id", True),
    )
    for child, column, parent, parent_key, nullable in relations:
        values = tables[child][column]
        invalid = ~values.isin(tables[parent][parent_key])
        if nullable:
            invalid &= values.notna()
        collector.mask(
            f"fk.{child}.{column}",
            "integrity",
            "critical",
            (child, parent),
            invalid,
            f"{child}.{column} has no orphan references to {parent}.{parent_key}",
        )


def _quantity_and_economic_gates(
    collector: _Collector,
    tables: Mapping[str, pd.DataFrame],
) -> None:
    order_lines = tables["order_lines"]
    delivery_lines = tables["delivery_lines"]
    inventory = tables["inventory"]
    products = tables["products"]
    vehicles = tables["vehicles"]
    costs = tables["cost_activities"]

    collector.mask(
        "quantity.ordered_positive", "validity", "high", ("order_lines",),
        order_lines["ordered_quantity"].le(0), "ordered quantities are greater than zero",
    )
    collector.mask(
        "quantity.delivered_positive", "validity", "high", ("delivery_lines",),
        delivery_lines["delivered_quantity"].le(0), "delivered quantities are greater than zero",
    )
    delivered = delivery_lines.groupby("order_line_id", dropna=False)[
        "delivered_quantity"
    ].sum()
    cumulative = order_lines["order_line_id"].map(delivered).fillna(0)
    collector.mask(
        "quantity.no_overdelivery", "consistency", "critical",
        ("order_lines", "delivery_lines"),
        cumulative.gt(order_lines["ordered_quantity"]),
        "cumulative delivered quantity never exceeds ordered quantity",
    )
    inventory_columns = [
        "on_hand_quantity", "allocated_quantity", "available_quantity",
        "safety_stock_quantity", "reorder_point_quantity",
    ]
    collector.mask(
        "quantity.inventory_nonnegative", "validity", "high", ("inventory",),
        inventory[inventory_columns].lt(0).any(axis=1),
        "all inventory quantities are non-negative",
    )
    collector.mask(
        "quantity.inventory_allocation", "consistency", "high", ("inventory",),
        inventory["allocated_quantity"].gt(inventory["on_hand_quantity"]),
        "allocated inventory does not exceed on-hand inventory",
    )
    collector.mask(
        "quantity.inventory_equation", "consistency", "high", ("inventory",),
        ~_close(
            inventory["available_quantity"],
            inventory["on_hand_quantity"] - inventory["allocated_quantity"],
            0.001,
        ),
        "available quantity reconciles to on-hand less allocated",
    )
    collector.mask(
        "quantity.inventory_thresholds", "consistency", "high", ("inventory",),
        inventory["reorder_point_quantity"].lt(inventory["safety_stock_quantity"]),
        "reorder point is not below safety stock",
    )
    collector.mask(
        "quantity.inventory_flags", "consistency", "high", ("inventory",),
        inventory["is_stockout"].ne(inventory["available_quantity"].eq(0))
        | inventory["is_low_inventory"].ne(
            inventory["available_quantity"].gt(0)
            & inventory["available_quantity"].le(inventory["reorder_point_quantity"])
        ),
        "stockout and low-inventory flags reconcile to available quantity",
    )
    deliveries = tables["deliveries"]
    collector.mask(
        "quantity.delivery_values", "validity", "high", ("deliveries",),
        deliveries["delivery_sequence"].le(0) | deliveries["distance_km"].lt(0),
        "delivery sequence is positive and distance is non-negative",
    )

    product_invalid = (
        products["reference_list_unit_price"].le(0)
        | products["reference_variable_unit_cost"].lt(0)
        | products["weight_kg"].le(0)
        | products["volume_m3"].le(0)
    )
    collector.mask(
        "economics.product_reference", "validity", "high", ("products",),
        product_invalid, "product prices, costs, weight and volume are valid",
    )
    vehicle_invalid = (
        vehicles["capacity_kg"].le(0)
        | vehicles["capacity_m3"].le(0)
        | vehicles["fixed_cost_day"].lt(0)
        | vehicles["variable_cost_km"].lt(0)
    )
    collector.mask(
        "economics.vehicle_reference", "validity", "high", ("vehicles",),
        vehicle_invalid, "vehicle capacity and reference costs are valid",
    )
    line_invalid = (
        order_lines["list_unit_price"].le(0)
        | order_lines["synthetic_discount_per_unit"].lt(0)
        | order_lines["synthetic_discount_per_unit"].gt(order_lines["list_unit_price"])
        | order_lines["unit_variable_cost"].lt(0)
    )
    collector.mask(
        "economics.line_ranges", "validity", "high", ("order_lines",),
        line_invalid, "transactional prices, discounts and variable costs are valid",
    )
    collector.mask(
        "economics.net_unit_price", "consistency", "high", ("order_lines",),
        ~_close(
            order_lines["net_unit_price"],
            order_lines["list_unit_price"] - order_lines["synthetic_discount_per_unit"],
            0.01,
        ),
        "net unit price reconciles to list price less discount",
    )
    collector.mask(
        "economics.ordered_net_sales", "consistency", "high", ("order_lines",),
        ~_close(
            order_lines["ordered_net_sales"],
            order_lines["ordered_quantity"] * order_lines["net_unit_price"],
            0.01,
        ),
        "ordered net sales reconciles at line grain",
    )
    cost_invalid = costs["cost_amount"].lt(0) | costs["cost_driver_value"].lt(0).fillna(False)
    collector.mask(
        "economics.cost_nonnegative", "validity", "high", ("cost_activities",),
        cost_invalid, "cost amounts and present driver values are non-negative",
    )


def _temporal_gates(
    collector: _Collector,
    tables: Mapping[str, pd.DataFrame],
) -> None:
    orders = tables["orders"]
    deliveries = tables["deliveries"]
    costs = tables["cost_activities"]

    requested_present = orders["requested_delivery_datetime"].notna()
    requested_invalid = requested_present & orders["requested_delivery_datetime"].lt(
        orders["order_datetime"]
    )
    collector.mask(
        "time.order_requested", "consistency", "high", ("orders",),
        requested_invalid, "requested delivery is null or not before order time",
    )
    collector.mask(
        "time.order_promised", "consistency", "high", ("orders",),
        orders["promised_delivery_datetime"].lt(orders["order_datetime"]),
        "promised delivery is not before order time",
    )
    delivery_time = deliveries.merge(
        orders[["order_id", "order_datetime"]],
        on="order_id",
        how="left",
        validate="many_to_one",
    )
    collector.mask(
        "time.delivery_dispatch", "consistency", "high", ("orders", "deliveries"),
        delivery_time["dispatch_datetime"].lt(delivery_time["order_datetime"]),
        "dispatch is not before order time",
    )
    collector.mask(
        "time.delivery_event", "consistency", "high", ("deliveries",),
        deliveries["delivery_datetime"].lt(deliveries["dispatch_datetime"]),
        "delivery is not before dispatch",
    )
    cost_time = costs.merge(
        orders[["order_id", "order_datetime"]],
        on="order_id",
        how="left",
        validate="many_to_one",
    )
    collector.mask(
        "time.cost_activity", "consistency", "high",
        ("orders", "cost_activities"),
        cost_time["activity_datetime"].lt(cost_time["order_datetime"]),
        "cost activity is not before order time",
    )


def _cross_dataset_gates(
    collector: _Collector,
    tables: Mapping[str, pd.DataFrame],
    config: ScenarioConfig,
) -> None:
    customers = tables["customers"]
    products = tables["products"]
    sites = tables["operational_sites"]
    orders = tables["orders"]
    order_lines = tables["order_lines"]
    deliveries = tables["deliveries"]
    delivery_lines = tables["delivery_lines"]
    vehicles = tables["vehicles"]
    inventory = tables["inventory"]
    costs = tables["cost_activities"]

    collector.mask(
        "grain.order_sku", "uniqueness", "critical", ("order_lines",),
        order_lines.duplicated(["order_id", "sku_id"], keep=False),
        "each SKU appears at most once within an order",
    )
    collector.mask(
        "grain.delivery_sequence", "uniqueness", "critical", ("deliveries",),
        deliveries.duplicated(["order_id", "delivery_sequence"], keep=False),
        "delivery sequence is unique within an order",
    )
    collector.mask(
        "grain.delivery_order_line", "uniqueness", "critical", ("delivery_lines",),
        delivery_lines.duplicated(["delivery_id", "order_line_id"], keep=False),
        "an order line appears once per delivery event",
    )

    line_order = order_lines.set_index("order_line_id")["order_id"]
    delivery_order = deliveries.set_index("delivery_id")["order_id"]
    delivery_line_order = delivery_lines["delivery_id"].map(delivery_order)
    collector.mask(
        "lineage.delivery_line_order", "integrity", "critical",
        ("delivery_lines", "deliveries", "order_lines"),
        delivery_line_order.ne(delivery_lines["order_line_id"].map(line_order)),
        "delivery and order line belong to the same order",
    )
    order_customer = orders.set_index("order_id")["customer_id"]
    customer_location = customers.set_index("customer_id")["location_id"]
    expected_location = deliveries["order_id"].map(order_customer).map(customer_location)
    collector.mask(
        "lineage.delivery_destination", "integrity", "critical",
        ("deliveries", "orders", "customers"),
        deliveries["destination_location_id"].ne(expected_location),
        "delivery destination equals the ordering customer's location",
    )
    cost_delivery_order = costs["delivery_id"].map(delivery_order)
    has_delivery = costs["delivery_id"].notna()
    collector.mask(
        "lineage.cost_delivery_order", "integrity", "critical",
        ("cost_activities", "deliveries"),
        has_delivery & costs["order_id"].ne(cost_delivery_order),
        "delivery-attributed cost belongs to the same order as its delivery",
    )
    collector.mask(
        "lineage.cost_delivery_required", "completeness", "high",
        ("cost_activities",),
        costs["cost_type"].isin(["transport", "delivery"]) & ~has_delivery,
        "transport and delivery cost activities identify a delivery",
    )
    collector.mask(
        "lineage.cost_driver_unit", "completeness", "high",
        ("cost_activities",),
        costs["cost_driver_value"].notna() & costs["cost_driver_unit"].isna(),
        "a present cost driver always declares its unit",
    )

    lines_per_order = order_lines.groupby("order_id").size()
    collector.mask(
        "cardinality.order_lines", "completeness", "critical",
        ("orders", "order_lines"),
        ~orders["order_id"].isin(lines_per_order.index),
        "every order contains at least one order line",
    )
    lines_per_delivery = delivery_lines.groupby("delivery_id").size()
    collector.mask(
        "cardinality.delivery_lines", "completeness", "critical",
        ("deliveries", "delivery_lines"),
        ~deliveries["delivery_id"].isin(lines_per_delivery.index),
        "every delivery contains at least one delivery line",
    )

    delivered = delivery_lines.groupby("order_line_id")["delivered_quantity"].sum()
    delivered_per_line = order_lines["order_line_id"].map(delivered).fillna(0)
    line_full = delivered_per_line.ge(
        order_lines["ordered_quantity"]
    )
    order_full = pd.Series(line_full.to_numpy(), index=order_lines["order_id"]).groupby(level=0).all()
    delivered_per_order = pd.Series(
        delivered_per_line.to_numpy(), index=order_lines["order_id"]
    ).groupby(level=0).sum()
    expected_status = pd.Series("confirmed", index=orders.index, dtype="string")
    has_delivery = orders["order_id"].map(delivered_per_order).fillna(0).gt(0)
    is_full = orders["order_id"].map(order_full).fillna(False)
    expected_status.loc[has_delivery] = "partially_fulfilled"
    expected_status.loc[is_full] = "fulfilled"
    collector.mask(
        "consistency.order_status", "consistency", "high",
        ("orders", "order_lines", "delivery_lines"),
        orders["order_status"].ne(expected_status),
        "order status reconciles with cumulative delivered quantities",
    )

    expected_dates = pd.date_range(config.period_start, config.period_end, freq="D")
    expected_inventory = pd.MultiIndex.from_product(
        [expected_dates, sites["site_id"].dropna(), products["sku_id"].dropna()],
        names=["snapshot_date", "site_id", "sku_id"],
    )
    actual_inventory = pd.MultiIndex.from_frame(
        inventory[["snapshot_date", "site_id", "sku_id"]]
    )
    coverage_violations = len(expected_inventory.difference(actual_inventory)) + len(
        actual_inventory.difference(expected_inventory)
    )
    collector.add(
        "coverage.inventory_daily", "completeness", "critical", ("inventory",),
        len(expected_inventory), coverage_violations,
        "one daily snapshot exists for every date × site × SKU",
    )

    delivery_detail = (
        delivery_lines
        .merge(
            order_lines[["order_line_id", "sku_id"]],
            on="order_line_id",
            how="left",
            validate="many_to_one",
        )
        .merge(
            products[["sku_id", "weight_kg", "volume_m3"]],
            on="sku_id",
            how="left",
            validate="many_to_one",
        )
    )
    delivery_detail["weight"] = (
        delivery_detail["delivered_quantity"] * delivery_detail["weight_kg"]
    )
    delivery_detail["volume"] = (
        delivery_detail["delivered_quantity"] * delivery_detail["volume_m3"]
    )
    loads = delivery_detail.groupby("delivery_id")[["weight", "volume"]].sum()
    capacity = (
        deliveries[["delivery_id", "vehicle_id"]]
        .merge(
            vehicles[["vehicle_id", "capacity_kg", "capacity_m3"]],
            on="vehicle_id",
            how="left",
            validate="many_to_one",
        )
        .set_index("delivery_id")
    )
    capacity_invalid = loads["weight"].gt(capacity["capacity_kg"]) | loads[
        "volume"
    ].gt(capacity["capacity_m3"])
    collector.mask(
        "capacity.delivery_vehicle", "validity", "high",
        ("delivery_lines", "products", "deliveries", "vehicles"),
        capacity_invalid, "delivery weight and volume fit assigned vehicle capacity",
    )
    location_type = tables["locations"].set_index("location_id")["location_type"]
    collector.mask(
        "lineage.customer_location_type", "integrity", "high",
        ("customers", "locations"),
        customers["location_id"].map(location_type).ne("customer"),
        "customer foreign keys reference customer-type locations",
    )
    collector.mask(
        "lineage.site_location_type", "integrity", "high",
        ("operational_sites", "locations"),
        sites["location_id"].map(location_type).ne("site"),
        "operational site foreign keys reference site-type locations",
    )

    created_date = customers.set_index("customer_id")["created_date"]
    collector.mask(
        "time.customer_created", "consistency", "high", ("customers", "orders"),
        orders["order_datetime"].dt.tz_localize(None).dt.normalize().lt(
            orders["customer_id"].map(created_date)
        ),
        "order date is not before customer creation date",
    )


def _geography_and_provenance_gates(
    collector: _Collector,
    tables: Mapping[str, pd.DataFrame],
) -> None:
    locations = tables["locations"]
    geo_invalid = (
        ~locations["latitude"].between(-90, 90, inclusive="both")
        | ~locations["longitude"].between(-180, 180, inclusive="both")
    )
    collector.mask(
        "geography.coordinates", "validity", "high", ("locations",),
        geo_invalid, "latitude and longitude are within valid bounds",
    )
    location_provenance = (
        locations["data_class"].eq("synthetic") & ~locations["is_synthetic"]
    ) | (
        locations["data_class"].eq("reference_location")
        & locations["is_synthetic"]
    )
    collector.mask(
        "provenance.locations", "consistency", "critical", ("locations",),
        location_provenance, "location is_synthetic agrees with data_class",
    )
    non_location_violations = 0
    rows = 0
    datasets: list[str] = []
    for name, table in tables.items():
        if name == "locations":
            continue
        datasets.append(name)
        rows += len(table)
        non_location_violations += int(table["is_synthetic"].ne(True).fillna(True).sum())
    collector.add(
        "provenance.operational", "validity", "critical", tuple(datasets), rows,
        non_location_violations,
        "all operational records are explicitly identified as synthetic",
    )


def _service_metrics(tables: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    orders = tables["orders"]
    order_lines = tables["order_lines"]
    deliveries = tables["deliveries"]
    delivery_lines = tables["delivery_lines"]

    detail = (
        delivery_lines[["delivery_id", "order_line_id", "delivered_quantity"]]
        .merge(
            deliveries[["delivery_id", "delivery_datetime"]],
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
    completed_line_events = detail[
        detail["cumulative_delivered"].ge(detail["ordered_quantity"])
    ]
    line_completion = completed_line_events.groupby("order_line_id")[
        "delivery_datetime"
    ].min()
    delivered_by_line = detail.groupby("order_line_id")["delivered_quantity"].sum()

    line_state = order_lines[["order_line_id", "order_id", "ordered_quantity"]].copy()
    line_state["delivered_quantity"] = (
        line_state["order_line_id"].map(delivered_by_line).fillna(0)
    )
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
    service["in_full"] = service["order_id"].map(order_full).fillna(False)
    service["completion_datetime"] = service["order_id"].map(order_completion)
    service["any_on_time"] = service["order_id"].map(any_on_time).fillna(False)
    service["service_class"] = "partial_late"
    service.loc[
        ~service["in_full"] & service["any_on_time"], "service_class"
    ] = "partial_on_time"
    service.loc[
        service["in_full"]
        & service["completion_datetime"].gt(service["promised_delivery_datetime"]),
        "service_class",
    ] = "complete_late"
    service.loc[
        service["in_full"]
        & service["completion_datetime"].le(service["promised_delivery_datetime"]),
        "service_class",
    ] = "complete_on_time"
    return service


def _coverage_and_control_gates(
    collector: _Collector,
    tables: Mapping[str, pd.DataFrame],
    config: ScenarioConfig,
) -> dict[str, Any]:
    row_counts = {name: len(table) for name, table in tables.items()}
    exact_counts = {
        "customers": config.customers_exact,
        "products": config.skus_exact,
        "vehicles": config.vehicles_exact,
        "operational_sites": config.operational_sites_exact,
    }
    for name, expected in exact_counts.items():
        collector.add(
            f"volume.{name}", "volume", "high", (name,), expected,
            abs(row_counts[name] - expected), f"{name} row count equals configured exact count",
        )
    order_min = config.orders_target * (1 - config.orders_tolerance_pct / 100)
    order_max = config.orders_target * (1 + config.orders_tolerance_pct / 100)
    order_violations = int(not order_min <= row_counts["orders"] <= order_max)
    collector.add(
        "volume.orders", "volume", "high", ("orders",), config.orders_target,
        order_violations, "order count is within configured tolerance",
    )
    line_min = config.order_lines_target * (1 - config.order_lines_tolerance_pct / 100)
    line_max = config.order_lines_target * (1 + config.order_lines_tolerance_pct / 100)
    line_violations = int(not line_min <= row_counts["order_lines"] <= line_max)
    collector.add(
        "volume.order_lines", "volume", "high", ("order_lines",),
        config.order_lines_target, line_violations,
        "order-line count is within configured tolerance",
    )

    orders = tables["orders"]
    promise_dates = orders["promised_delivery_datetime"].dt.date
    eligible = promise_dates.ge(config.period_start) & promise_dates.le(config.period_end)
    service = _service_metrics(tables)
    service = service.loc[eligible.to_numpy()]
    service_counts = service["service_class"].value_counts().to_dict()
    eligible_count = len(service)
    thresholds = {
        "complete_on_time": 0.60,
        "complete_late": 0.05,
        "partial_on_time": 0.05,
        "partial_late": 0.05,
    }
    service_shares: dict[str, float] = {}
    for class_name, threshold in thresholds.items():
        count = int(service_counts.get(class_name, 0))
        share = count / eligible_count if eligible_count else 0.0
        service_shares[class_name] = round(share, 6)
        shortfall = max(0, math_ceil(threshold * eligible_count) - count)
        collector.add(
            f"coverage.service.{class_name}", "coverage", "high",
            ("orders", "order_lines", "deliveries", "delivery_lines"),
            eligible_count, shortfall,
            f"{class_name} share is at least {threshold:.0%} of eligible orders",
        )

    inventory = tables["inventory"]
    stockout_rate = float(inventory["is_stockout"].mean()) if len(inventory) else 0.0
    low_inventory_rate = (
        float(inventory["is_low_inventory"].mean()) if len(inventory) else 0.0
    )
    collector.add(
        "coverage.stockout", "coverage", "medium", ("inventory",), len(inventory),
        max(0, math_ceil(0.01 * len(inventory)) - int(inventory["is_stockout"].sum())),
        "stockout observations cover at least 1% of inventory snapshots",
    )
    collector.add(
        "coverage.low_inventory", "coverage", "medium", ("inventory",), len(inventory),
        max(
            0,
            math_ceil(0.05 * len(inventory))
            - int(inventory["is_low_inventory"].sum()),
        ),
        "low-inventory observations cover at least 5% of inventory snapshots",
    )

    order_lines = tables["order_lines"]
    delivery_lines = tables["delivery_lines"]
    order_customer = orders.set_index("order_id")["customer_id"]
    sales_detail = delivery_lines.merge(
        order_lines[["order_line_id", "order_id", "net_unit_price", "unit_variable_cost"]],
        on="order_line_id",
        how="left",
        validate="many_to_one",
    )
    sales_detail["recognized_net_sales"] = (
        sales_detail["delivered_quantity"] * sales_detail["net_unit_price"]
    )
    sales_detail["variable_product_cost"] = (
        sales_detail["delivered_quantity"] * sales_detail["unit_variable_cost"]
    )
    sales_detail["customer_id"] = sales_detail["order_id"].map(order_customer)
    customers = tables["customers"]["customer_id"]
    customer_sales = sales_detail.groupby("customer_id")["recognized_net_sales"].sum()
    costs = tables["cost_activities"].copy()
    costs["customer_id"] = costs["order_id"].map(order_customer)
    customer_cts = costs.groupby("customer_id")["cost_amount"].sum()
    customer_metrics = pd.DataFrame({"customer_id": customers})
    customer_metrics["sales"] = customer_metrics["customer_id"].map(customer_sales).fillna(0)
    customer_metrics["cts"] = customer_metrics["customer_id"].map(customer_cts).fillna(0)
    sales_median = float(customer_metrics["sales"].median())
    cts_median = float(customer_metrics["cts"].median())
    customer_metrics["quadrant"] = (
        customer_metrics["sales"].ge(sales_median).map({True: "high", False: "low"})
        + "_sales_"
        + customer_metrics["cts"].ge(cts_median).map({True: "high", False: "low"})
        + "_cts"
    )
    expected_quadrants = {
        "high_sales_high_cts", "high_sales_low_cts", "low_sales_high_cts",
        "low_sales_low_cts",
    }
    quadrant_counts = {
        name: int((customer_metrics["quadrant"] == name).sum())
        for name in sorted(expected_quadrants)
    }
    quadrant_shortfall = sum(max(0, 5 - count) for count in quadrant_counts.values())
    collector.add(
        "coverage.customer_quadrants", "coverage", "high",
        ("customers", "orders", "order_lines", "delivery_lines", "cost_activities"),
        len(customer_metrics), quadrant_shortfall,
        "each sales/CTS median quadrant contains at least five customers",
    )

    cost_types = set(costs["cost_type"].dropna().astype(str))
    required_cost_types = {
        "order_processing", "picking", "handling", "transport", "delivery", "incident",
    }
    collector.add(
        "coverage.cost_components", "coverage", "high", ("cost_activities",),
        len(required_cost_types), len(required_cost_types - cost_types),
        "all six minimum CTS components are represented",
    )

    recognized_sales = float(sales_detail["recognized_net_sales"].sum())
    variable_cost = float(sales_detail["variable_product_cost"].sum())
    cts = float(costs["cost_amount"].sum())
    contribution_margin = recognized_sales - variable_cost
    mc_cts = contribution_margin - cts
    return {
        "row_counts": row_counts,
        "eligible_orders": eligible_count,
        "service_class_counts": {
            name: int(service_counts.get(name, 0)) for name in thresholds
        },
        "service_class_shares": service_shares,
        "stockout_rate": round(stockout_rate, 6),
        "low_inventory_rate": round(low_inventory_rate, 6),
        "customer_quadrant_counts": quadrant_counts,
        "control_totals": {
            "recognized_net_sales": round(recognized_sales, 2),
            "variable_product_cost": round(variable_cost, 2),
            "contribution_margin": round(contribution_margin, 2),
            "cost_to_serve": round(cts, 2),
            "mc_cts": round(mc_cts, 2),
        },
    }


def math_ceil(value: float) -> int:
    return int(np.ceil(value))


def validate_loaded_source(
    loaded: LoadedSource,
    schema: DataContractSchema,
    config: ScenarioConfig,
) -> ValidationOutcome:
    """Run all D02 quality gates and return inspectable evidence."""

    collector = _Collector()
    _schema_gates(collector, loaded, schema)
    if loaded.findings:
        return ValidationOutcome(
            status="failed",
            schema_version=schema.schema_version,
            dataset_build_id=None,
            tables=loaded.tables,
            results=tuple(collector.results),
            metrics={
                "row_counts": {
                    name: len(table) for name, table in loaded.tables.items()
                }
            },
        )
    build_id = _identity_and_key_gates(collector, loaded.tables, schema, config)
    structural_failure = any(
        result.status == "failed"
        and (result.gate_id.startswith("pk.") or result.gate_id.startswith("lineage."))
        for result in collector.results
    )
    if structural_failure:
        return ValidationOutcome(
            status="failed",
            schema_version=schema.schema_version,
            dataset_build_id=build_id,
            tables=loaded.tables,
            results=tuple(collector.results),
            metrics={
                "row_counts": {
                    name: len(table) for name, table in loaded.tables.items()
                }
            },
        )
    _foreign_key_gates(collector, loaded.tables)
    _quantity_and_economic_gates(collector, loaded.tables)
    _temporal_gates(collector, loaded.tables)
    _cross_dataset_gates(collector, loaded.tables, config)
    _geography_and_provenance_gates(collector, loaded.tables)
    metrics = _coverage_and_control_gates(collector, loaded.tables, config)
    results = tuple(collector.results)
    return ValidationOutcome(
        status="passed" if all(result.status == "passed" for result in results) else "failed",
        schema_version=schema.schema_version,
        dataset_build_id=build_id,
        tables=loaded.tables,
        results=results,
        metrics=metrics,
    )
