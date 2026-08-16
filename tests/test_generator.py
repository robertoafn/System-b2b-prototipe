from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import pytest

from src.config import load_scenario_config
from src.synthetic.generator import (
    DATASET_COLUMNS,
    DATASET_ORDER,
    GeneratedSyntheticData,
    generate_synthetic_data,
    publish_synthetic_csvs,
)


ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG = ROOT / "config" / "scenario_base.yaml"


@pytest.fixture(scope="module")
def generated() -> GeneratedSyntheticData:
    return generate_synthetic_data(load_scenario_config(BASE_CONFIG))


def _digest(table: pd.DataFrame) -> str:
    payload = table.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return sha256(payload).hexdigest().upper()


def test_dataset_set_counts_columns_and_provenance(
    generated: GeneratedSyntheticData,
) -> None:
    tables = generated.tables
    assert tuple(tables) == DATASET_ORDER
    assert len(tables["customers"]) == 150
    assert len(tables["products"]) == 30
    assert len(tables["locations"]) == 151
    assert len(tables["operational_sites"]) == 1
    assert len(tables["vehicles"]) == 6
    assert len(tables["orders"]) == 4000
    assert len(tables["order_lines"]) == 10000
    assert len(tables["inventory"]) == 10950
    assert len(tables["deliveries"]) == 5000
    assert len(tables["delivery_lines"]) >= len(tables["order_lines"])
    assert len(tables["cost_activities"]) > 22000

    for name, table in tables.items():
        assert tuple(table.columns) == DATASET_COLUMNS[name]
        assert set(table["scenario_id"]) == {"B2B-V1-BASE"}
        assert set(table["dataset_build_id"]) == {generated.dataset_build_id}
        assert table["is_synthetic"].eq(True).all()  # noqa: E712


def test_generation_is_exactly_repeatable(generated: GeneratedSyntheticData) -> None:
    repeated = generate_synthetic_data(load_scenario_config(BASE_CONFIG))

    assert repeated.dataset_build_id == generated.dataset_build_id
    assert {
        name: _digest(table) for name, table in repeated.tables.items()
    } == {
        name: _digest(table) for name, table in generated.tables.items()
    }


def test_primary_foreign_and_composite_keys(
    generated: GeneratedSyntheticData,
) -> None:
    tables = generated.tables
    primary_keys = {
        "customers": "customer_id",
        "products": "sku_id",
        "locations": "location_id",
        "operational_sites": "site_id",
        "vehicles": "vehicle_id",
        "orders": "order_id",
        "order_lines": "order_line_id",
        "deliveries": "delivery_id",
        "delivery_lines": "delivery_line_id",
        "cost_activities": "cost_activity_id",
    }
    for name, key in primary_keys.items():
        assert tables[name][key].notna().all()
        assert tables[name][key].is_unique

    inventory_key = ["snapshot_date", "site_id", "sku_id"]
    assert not tables["inventory"].duplicated(inventory_key).any()
    assert not tables["order_lines"].duplicated(["order_id", "sku_id"]).any()
    assert not tables["deliveries"].duplicated(
        ["order_id", "delivery_sequence"]
    ).any()
    assert not tables["delivery_lines"].duplicated(
        ["delivery_id", "order_line_id"]
    ).any()

    assert set(tables["customers"]["location_id"]) <= set(
        tables["locations"]["location_id"]
    )
    assert set(tables["orders"]["customer_id"]) <= set(
        tables["customers"]["customer_id"]
    )
    assert set(tables["order_lines"]["order_id"]) <= set(
        tables["orders"]["order_id"]
    )
    assert set(tables["order_lines"]["sku_id"]) <= set(
        tables["products"]["sku_id"]
    )
    assert set(tables["deliveries"]["vehicle_id"]) <= set(
        tables["vehicles"]["vehicle_id"]
    )
    assert set(tables["delivery_lines"]["delivery_id"]) <= set(
        tables["deliveries"]["delivery_id"]
    )
    assert set(tables["delivery_lines"]["order_line_id"]) <= set(
        tables["order_lines"]["order_line_id"]
    )


def test_inventory_daily_coverage_and_states(
    generated: GeneratedSyntheticData,
) -> None:
    inventory = generated.tables["inventory"]
    assert inventory["snapshot_date"].nunique() == 365
    assert inventory.groupby("snapshot_date").size().eq(30).all()
    assert (
        inventory["available_quantity"]
        == inventory["on_hand_quantity"] - inventory["allocated_quantity"]
    ).all()
    assert (inventory["allocated_quantity"] <= inventory["on_hand_quantity"]).all()
    assert inventory["is_stockout"].eq(inventory["available_quantity"].eq(0)).all()
    expected_low = inventory["available_quantity"].gt(0) & inventory[
        "available_quantity"
    ].le(inventory["reorder_point_quantity"])
    assert inventory["is_low_inventory"].eq(expected_low).all()
    assert inventory["is_stockout"].mean() >= 0.01
    assert inventory["is_low_inventory"].mean() >= 0.05


def test_temporal_and_cross_dataset_delivery_rules(
    generated: GeneratedSyntheticData,
) -> None:
    tables = generated.tables
    orders = tables["orders"].copy()
    deliveries = tables["deliveries"].copy()
    orders["order_ts"] = pd.to_datetime(orders["order_datetime"], utc=True)
    orders["promise_ts"] = pd.to_datetime(
        orders["promised_delivery_datetime"], utc=True
    )
    requested = pd.to_datetime(orders["requested_delivery_datetime"], utc=True)
    assert orders["order_ts"].le(orders["promise_ts"]).all()
    assert orders.loc[requested.notna(), "order_ts"].le(requested.dropna()).all()

    deliveries["dispatch_ts"] = pd.to_datetime(
        deliveries["dispatch_datetime"], utc=True
    )
    deliveries["delivery_ts"] = pd.to_datetime(
        deliveries["delivery_datetime"], utc=True
    )
    delivery_time = deliveries.merge(
        orders[["order_id", "order_ts"]], on="order_id", validate="many_to_one"
    )
    assert delivery_time["order_ts"].le(delivery_time["dispatch_ts"]).all()
    assert delivery_time["dispatch_ts"].le(delivery_time["delivery_ts"]).all()

    expected_destination = (
        tables["orders"]
        .merge(
            tables["customers"][["customer_id", "location_id"]],
            on="customer_id",
            validate="many_to_one",
        )
        .set_index("order_id")["location_id"]
    )
    actual_destination = deliveries.set_index("order_id")["destination_location_id"]
    assert actual_destination.eq(actual_destination.index.map(expected_destination)).all()

    lineage = (
        tables["delivery_lines"]
        .merge(
            deliveries[["delivery_id", "order_id"]],
            on="delivery_id",
            validate="many_to_one",
        )
        .merge(
            tables["order_lines"][["order_line_id", "order_id"]],
            on="order_line_id",
            suffixes=("_delivery", "_line"),
            validate="many_to_one",
        )
    )
    assert lineage["order_id_delivery"].eq(lineage["order_id_line"]).all()


def test_quantities_service_classes_and_order_status(
    generated: GeneratedSyntheticData,
) -> None:
    tables = generated.tables
    orders = tables["orders"].copy()
    order_lines = tables["order_lines"].copy()
    deliveries = tables["deliveries"].copy()
    delivery_lines = tables["delivery_lines"].copy()

    delivered_by_line = delivery_lines.groupby("order_line_id")[
        "delivered_quantity"
    ].sum()
    order_lines["delivered_quantity"] = (
        order_lines["order_line_id"].map(delivered_by_line).fillna(0)
    )
    assert order_lines["delivered_quantity"].gt(0).all()
    assert order_lines["delivered_quantity"].le(order_lines["ordered_quantity"]).all()
    order_lines["line_full"] = order_lines["delivered_quantity"].eq(
        order_lines["ordered_quantity"]
    )
    in_full = order_lines.groupby("order_id")["line_full"].all()

    deliveries["delivery_ts"] = pd.to_datetime(
        deliveries["delivery_datetime"], utc=True
    )
    orders["promise_ts"] = pd.to_datetime(
        orders["promised_delivery_datetime"], utc=True
    )
    promise = orders.set_index("order_id")["promise_ts"]
    completion = deliveries.groupby("order_id")["delivery_ts"].max()
    delivery_with_promise = deliveries.assign(
        promise_ts=deliveries["order_id"].map(promise)
    )
    any_on_time = delivery_with_promise.assign(
        on_time=delivery_with_promise["delivery_ts"].le(
            delivery_with_promise["promise_ts"]
        )
    ).groupby("order_id")["on_time"].any()

    derived = pd.DataFrame(index=orders["order_id"])
    derived["in_full"] = derived.index.map(in_full)
    derived["completion"] = derived.index.map(completion)
    derived["promise"] = derived.index.map(promise)
    derived["any_on_time"] = derived.index.map(any_on_time)
    derived["service_class"] = "partial_late"
    derived.loc[~derived["in_full"] & derived["any_on_time"], "service_class"] = (
        "partial_on_time"
    )
    derived.loc[
        derived["in_full"] & derived["completion"].gt(derived["promise"]),
        "service_class",
    ] = "complete_late"
    derived.loc[
        derived["in_full"] & derived["completion"].le(derived["promise"]),
        "service_class",
    ] = "complete_on_time"
    shares = derived["service_class"].value_counts(normalize=True)
    assert shares["complete_on_time"] >= 0.60
    assert shares["complete_late"] >= 0.05
    assert shares["partial_on_time"] >= 0.05
    assert shares["partial_late"] >= 0.05

    status = orders.set_index("order_id")["order_status"]
    assert status[derived["in_full"]].eq("fulfilled").all()
    assert status[~derived["in_full"]].eq("partially_fulfilled").all()


def test_capacity_cost_lineage_economics_and_customer_quadrants(
    generated: GeneratedSyntheticData,
) -> None:
    tables = generated.tables
    delivery_detail = (
        tables["delivery_lines"]
        .merge(
            tables["order_lines"][[
                "order_line_id", "order_id", "sku_id", "net_unit_price",
                "unit_variable_cost",
            ]],
            on="order_line_id",
            validate="many_to_one",
        )
        .merge(
            tables["products"][["sku_id", "weight_kg", "volume_m3"]],
            on="sku_id",
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
        tables["deliveries"][["delivery_id", "vehicle_id"]]
        .merge(
            tables["vehicles"][["vehicle_id", "capacity_kg", "capacity_m3"]],
            on="vehicle_id",
            validate="many_to_one",
        )
        .set_index("delivery_id")
    )
    assert loads["weight"].le(capacity["capacity_kg"]).all()
    assert loads["volume"].le(capacity["capacity_m3"]).all()

    costs = tables["cost_activities"]
    assert set(costs["cost_type"]) == {
        "order_processing", "picking", "handling", "transport", "delivery",
        "incident",
    }
    assert costs["cost_amount"].map(float).ge(0).all()
    assert costs["currency_code"].eq("CLP").all()
    assert costs.loc[costs["cost_type"].isin(["transport", "delivery"]), "delivery_id"].notna().all()
    delivery_order = tables["deliveries"].set_index("delivery_id")["order_id"]
    cost_with_delivery = costs[costs["delivery_id"].notna()]
    assert cost_with_delivery["order_id"].eq(
        cost_with_delivery["delivery_id"].map(delivery_order)
    ).all()

    delivery_detail["recognized_sales"] = (
        delivery_detail["delivered_quantity"]
        * delivery_detail["net_unit_price"].map(float)
    )
    order_customer = tables["orders"].set_index("order_id")["customer_id"]
    delivery_detail["customer_id"] = delivery_detail["order_id"].map(order_customer)
    customer_sales = delivery_detail.groupby("customer_id")["recognized_sales"].sum()
    costs = costs.assign(customer_id=costs["order_id"].map(order_customer))
    customer_cts = costs.assign(
        numeric_cost=costs["cost_amount"].map(float)
    ).groupby("customer_id")["numeric_cost"].sum()
    customer_metrics = pd.concat(
        [customer_sales.rename("sales"), customer_cts.rename("cts")], axis=1
    )
    sales_median = customer_metrics["sales"].median()
    cts_median = customer_metrics["cts"].median()
    customer_metrics["quadrant"] = (
        customer_metrics["sales"].ge(sales_median).map({True: "high", False: "low"})
        + "_sales_"
        + customer_metrics["cts"].ge(cts_median).map({True: "high", False: "low"})
        + "_cts"
    )
    quadrant_counts = customer_metrics["quadrant"].value_counts()
    assert set(quadrant_counts.index) == {
        "high_sales_high_cts", "high_sales_low_cts", "low_sales_high_cts",
        "low_sales_low_cts",
    }
    assert quadrant_counts.min() >= 5


def test_atomic_csv_publication_is_repeatable(
    generated: GeneratedSyntheticData,
) -> None:
    with TemporaryDirectory(prefix="publish-test-", dir=ROOT / "tests") as directory:
        output = Path(directory) / "synthetic"
        first_hashes = publish_synthetic_csvs(generated, output)
        second_hashes = publish_synthetic_csvs(generated, output)

        assert first_hashes == second_hashes
        assert sorted(path.stem for path in output.glob("*.csv")) == sorted(
            DATASET_ORDER
        )
        for name in DATASET_ORDER:
            round_trip = pd.read_csv(output / f"{name}.csv")
            assert tuple(round_trip.columns) == DATASET_COLUMNS[name]
            assert len(round_trip) == len(generated.tables[name])
            assert set(round_trip["scenario_id"]) == {"B2B-V1-BASE"}
            assert set(round_trip["dataset_build_id"]) == {
                generated.dataset_build_id
            }
        assert not list(output.parent.glob(".synthetic.staging-*"))
        assert not list(output.parent.glob(".synthetic.backup-*"))
