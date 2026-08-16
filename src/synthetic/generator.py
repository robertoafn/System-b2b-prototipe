"""Deterministic generator for the eleven V1.0 Core source datasets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import math
import os
from pathlib import Path
import shutil
from time import sleep
from typing import Any, Mapping
from uuid import uuid4
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src.config import ScenarioConfig


DATASET_ORDER = (
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

DATASET_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "customers": (
        "customer_id", "customer_name", "customer_segment", "location_id",
        "created_date", "is_active", "scenario_id", "dataset_build_id",
        "is_synthetic",
    ),
    "products": (
        "sku_id", "sku_name", "product_family", "unit",
        "reference_list_unit_price", "reference_variable_unit_cost",
        "weight_kg", "volume_m3", "is_active", "scenario_id",
        "dataset_build_id", "is_synthetic",
    ),
    "locations": (
        "location_id", "location_type", "commune", "region", "country_code",
        "latitude", "longitude", "data_class", "scenario_id",
        "dataset_build_id", "is_synthetic",
    ),
    "operational_sites": (
        "site_id", "location_id", "site_type", "is_active", "scenario_id",
        "dataset_build_id", "is_synthetic",
    ),
    "vehicles": (
        "vehicle_id", "vehicle_type", "capacity_kg", "capacity_m3",
        "fixed_cost_day", "variable_cost_km", "is_active", "scenario_id",
        "dataset_build_id", "is_synthetic",
    ),
    "orders": (
        "order_id", "customer_id", "order_datetime",
        "requested_delivery_datetime", "promised_delivery_datetime",
        "order_status", "scenario_id", "dataset_build_id", "is_synthetic",
    ),
    "order_lines": (
        "order_line_id", "order_id", "sku_id", "ordered_quantity",
        "list_unit_price", "synthetic_discount_per_unit", "net_unit_price",
        "unit_variable_cost", "ordered_net_sales", "scenario_id",
        "dataset_build_id", "is_synthetic",
    ),
    "inventory": (
        "snapshot_date", "site_id", "sku_id", "on_hand_quantity",
        "allocated_quantity", "available_quantity", "safety_stock_quantity",
        "reorder_point_quantity", "is_stockout", "is_low_inventory",
        "scenario_id", "dataset_build_id", "is_synthetic",
    ),
    "deliveries": (
        "delivery_id", "order_id", "vehicle_id", "origin_site_id",
        "destination_location_id", "delivery_sequence", "dispatch_datetime",
        "delivery_datetime", "distance_km", "delivery_status", "scenario_id",
        "dataset_build_id", "is_synthetic",
    ),
    "delivery_lines": (
        "delivery_line_id", "delivery_id", "order_line_id",
        "delivered_quantity", "scenario_id", "dataset_build_id",
        "is_synthetic",
    ),
    "cost_activities": (
        "cost_activity_id", "order_id", "delivery_id", "activity_datetime",
        "cost_type", "cost_amount", "currency_code", "cost_driver_value",
        "cost_driver_unit", "allocation_method", "scenario_id",
        "dataset_build_id", "is_synthetic",
    ),
}

_CENT = Decimal("0.01")
_SITE_ID = "SOR-01"
_SITE_LOCATION_ID = "LOC-SYN-SITE-001"
_SITE_LATITUDE = -33.3790
_SITE_LONGITUDE = -70.7350


@dataclass(frozen=True)
class GeneratedSyntheticData:
    dataset_build_id: str
    tables: Mapping[str, pd.DataFrame]


def _money(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(_CENT, rounding=ROUND_HALF_UP)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _build_id(config: ScenarioConfig) -> str:
    payload = "|".join(
        (
            config.scenario_id,
            str(config.seed),
            config.generator_version,
            config.schema_version,
            config.config_sha256,
        )
    ).encode("utf-8")
    return "BLD-" + hashlib.sha256(payload).hexdigest()[:20].upper()


def _common(config: ScenarioConfig, build_id: str) -> dict[str, Any]:
    return {
        "scenario_id": config.scenario_id,
        "dataset_build_id": build_id,
        "is_synthetic": True,
    }


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _generate_master_rows(
    config: ScenarioConfig,
    rng: np.random.Generator,
    build_id: str,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    common = _common(config, build_id)
    locations: list[dict[str, Any]] = [
        {
            "location_id": _SITE_LOCATION_ID,
            "location_type": "site",
            "commune": "Quilicura (referencia sintética)",
            "region": "Región Metropolitana de Santiago",
            "country_code": "CL",
            "latitude": _SITE_LATITUDE,
            "longitude": _SITE_LONGITUDE,
            "data_class": "synthetic",
            **common,
        }
    ]
    customers: list[dict[str, Any]] = []
    customer_specs: dict[str, dict[str, Any]] = {}
    near_communes = ("Quilicura", "Pudahuel", "Renca", "Conchalí")
    far_communes = ("Zona Norte", "Zona Sur", "Zona Oriente", "Zona Poniente")

    for number in range(1, config.customers_exact + 1):
        profile = (number - 1) % 4
        high_sales = profile in (0, 1)
        high_cts = profile in (1, 3)
        customer_id = f"CUS-SYN-{number:03d}"
        location_id = f"LOC-SYN-CUS-{number:03d}"

        if high_cts:
            latitude = float(-34.03 + rng.normal(0, 0.055))
            longitude = float(-71.17 + rng.normal(0, 0.055))
            commune = far_communes[number % len(far_communes)]
        else:
            latitude = float(-33.44 + rng.normal(0, 0.035))
            longitude = float(-70.69 + rng.normal(0, 0.035))
            commune = near_communes[number % len(near_communes)]

        locations.append(
            {
                "location_id": location_id,
                "location_type": "customer",
                "commune": commune,
                "region": "Región Metropolitana de Santiago",
                "country_code": "CL",
                "latitude": round(latitude, 6),
                "longitude": round(longitude, 6),
                "data_class": "synthetic",
                **common,
            }
        )
        created_date = config.period_start - timedelta(
            days=int(rng.integers(30, 1001))
        )
        customers.append(
            {
                "customer_id": customer_id,
                "customer_name": f"Cliente Sintético {number:03d}",
                "customer_segment": "enterprise" if high_sales else "mid_market",
                "location_id": location_id,
                "created_date": created_date.isoformat(),
                "is_active": True,
                "scenario_id": config.scenario_id,
                "dataset_build_id": build_id,
                "is_synthetic": True,
            }
        )
        customer_specs[customer_id] = {
            "customer_id": customer_id,
            "location_id": location_id,
            "latitude": latitude,
            "longitude": longitude,
            "high_sales": high_sales,
            "high_cts": high_cts,
        }

    products: list[dict[str, Any]] = []
    product_specs: dict[str, dict[str, Any]] = {}
    families = ("Familia A", "Familia B", "Familia C", "Familia D", "Familia E")
    for number in range(1, config.skus_exact + 1):
        sku_id = f"SKU-SYN-{number:03d}"
        list_price = _money(int(rng.integers(120, 1001)) * 100)
        unit_cost = _money(list_price * Decimal(str(rng.uniform(0.45, 0.72))))
        weight_kg = round(float(rng.uniform(0.5, 15.0)), 3)
        volume_m3 = round(float(rng.uniform(0.004, 0.075)), 4)
        products.append(
            {
                "sku_id": sku_id,
                "sku_name": f"Producto Sintético {number:03d}",
                "product_family": families[(number - 1) % len(families)],
                "unit": "unidad",
                "reference_list_unit_price": list_price,
                "reference_variable_unit_cost": unit_cost,
                "weight_kg": weight_kg,
                "volume_m3": volume_m3,
                "is_active": True,
                "scenario_id": config.scenario_id,
                "dataset_build_id": build_id,
                "is_synthetic": True,
            }
        )
        product_specs[sku_id] = {
            "sku_id": sku_id,
            "list_price": list_price,
            "unit_cost": unit_cost,
            "weight_kg": weight_kg,
            "volume_m3": volume_m3,
        }

    operational_sites = [
        {
            "site_id": _SITE_ID,
            "location_id": _SITE_LOCATION_ID,
            "site_type": "operational_logistics_node",
            "is_active": True,
            "scenario_id": config.scenario_id,
            "dataset_build_id": build_id,
            "is_synthetic": True,
        }
    ]

    vehicles: list[dict[str, Any]] = []
    vehicle_specs: dict[str, dict[str, Any]] = {}
    for number in range(1, config.vehicles_exact + 1):
        vehicle_id = f"VEH-SYN-{number:02d}"
        capacity_kg = 18_000 + number * 1_000
        capacity_m3 = 80 + number * 5
        variable_cost_km = _money(650 + number * 75)
        vehicles.append(
            {
                "vehicle_id": vehicle_id,
                "vehicle_type": "camión sintético",
                "capacity_kg": capacity_kg,
                "capacity_m3": capacity_m3,
                "fixed_cost_day": _money(85_000 + number * 5_000),
                "variable_cost_km": variable_cost_km,
                "is_active": True,
                "scenario_id": config.scenario_id,
                "dataset_build_id": build_id,
                "is_synthetic": True,
            }
        )
        vehicle_specs[vehicle_id] = {
            "vehicle_id": vehicle_id,
            "capacity_kg": capacity_kg,
            "capacity_m3": capacity_m3,
            "variable_cost_km": variable_cost_km,
        }

    rows = {
        "customers": customers,
        "products": products,
        "locations": locations,
        "operational_sites": operational_sites,
        "vehicles": vehicles,
    }
    context = {
        "customer_specs": customer_specs,
        "product_specs": product_specs,
        "vehicle_specs": vehicle_specs,
    }
    return rows, context


def _generate_orders_and_lines(
    config: ScenarioConfig,
    rng: np.random.Generator,
    build_id: str,
    customer_specs: Mapping[str, Mapping[str, Any]],
    product_specs: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    customer_ids = list(customer_specs)
    weights = np.array(
        [3.0 if customer_specs[item]["high_sales"] else 1.0 for item in customer_ids]
    )
    weights /= weights.sum()
    guaranteed_customers = customer_ids[: min(config.orders_target, len(customer_ids))]
    assignments = guaranteed_customers.copy()
    assignments.extend(
        str(value)
        for value in rng.choice(
            customer_ids,
            size=config.orders_target - len(guaranteed_customers),
            replace=True,
            p=weights,
        )
    )
    rng.shuffle(assignments)

    service_classes = (
        ["complete_on_time"] * int(config.orders_target * 0.70)
        + ["complete_late"] * int(config.orders_target * 0.10)
        + ["partial_on_time"] * int(config.orders_target * 0.10)
    )
    service_classes += ["partial_late"] * (
        config.orders_target - len(service_classes)
    )
    rng.shuffle(service_classes)

    if not config.orders_target <= config.order_lines_target <= (
        config.orders_target * config.skus_exact
    ):
        raise ValueError(
            "order_lines_target must allow at least one unique SKU per order"
        )
    base_lines, extra_lines = divmod(
        config.order_lines_target,
        config.orders_target,
    )
    line_counts = [base_lines + 1] * extra_lines
    line_counts += [base_lines] * (config.orders_target - extra_lines)
    rng.shuffle(line_counts)

    tz = ZoneInfo(config.timezone)
    last_order_date = config.period_end - timedelta(days=6)
    date_span = (last_order_date - config.period_start).days + 1
    drafts: list[dict[str, Any]] = []
    for sequence in range(config.orders_target):
        order_day = config.period_start + timedelta(days=int(rng.integers(0, date_span)))
        order_datetime = datetime.combine(
            order_day,
            time(
                hour=int(rng.integers(8, 18)),
                minute=int(rng.integers(0, 60)),
            ),
            tzinfo=tz,
        )
        promise_days = int(rng.integers(2, 7))
        promised_datetime = order_datetime + timedelta(days=promise_days)
        requested_datetime = None
        if rng.random() < 0.82:
            requested_datetime = order_datetime + timedelta(
                days=int(rng.integers(1, promise_days + 1))
            )
        drafts.append(
            {
                "sort_sequence": sequence,
                "customer_id": assignments[sequence],
                "service_class": service_classes[sequence],
                "line_count": line_counts[sequence],
                "order_datetime": order_datetime,
                "requested_datetime": requested_datetime,
                "promised_datetime": promised_datetime,
            }
        )
    drafts.sort(key=lambda item: (item["order_datetime"], item["sort_sequence"]))

    product_ids = list(product_specs)
    order_rows: list[dict[str, Any]] = []
    line_rows: list[dict[str, Any]] = []
    order_specs: list[dict[str, Any]] = []
    line_number = 0

    for order_number, draft in enumerate(drafts, start=1):
        order_id = f"ORD-SYN-{order_number:06d}"
        customer = customer_specs[draft["customer_id"]]
        service_class = draft["service_class"]
        order_status = (
            "fulfilled" if service_class.startswith("complete") else "partially_fulfilled"
        )
        order_rows.append(
            {
                "order_id": order_id,
                "customer_id": draft["customer_id"],
                "order_datetime": _iso(draft["order_datetime"]),
                "requested_delivery_datetime": (
                    _iso(draft["requested_datetime"])
                    if draft["requested_datetime"] is not None
                    else None
                ),
                "promised_delivery_datetime": _iso(draft["promised_datetime"]),
                "order_status": order_status,
                "scenario_id": config.scenario_id,
                "dataset_build_id": build_id,
                "is_synthetic": True,
            }
        )

        selected_products = [
            str(item)
            for item in rng.choice(
                product_ids,
                size=draft["line_count"],
                replace=False,
            )
        ]
        internal_lines: list[dict[str, Any]] = []
        for sku_id in selected_products:
            line_number += 1
            product = product_specs[sku_id]
            if customer["high_sales"]:
                ordered_quantity = int(rng.integers(20, 61))
            else:
                ordered_quantity = int(rng.integers(2, 13))
            discount_rate = Decimal(str(float(rng.uniform(0.00, 0.12))))
            discount = _money(product["list_price"] * discount_rate)
            net_price = _money(product["list_price"] - discount)
            ordered_sales = _money(Decimal(ordered_quantity) * net_price)
            order_line_id = f"OLN-SYN-{line_number:07d}"
            row = {
                "order_line_id": order_line_id,
                "order_id": order_id,
                "sku_id": sku_id,
                "ordered_quantity": ordered_quantity,
                "list_unit_price": product["list_price"],
                "synthetic_discount_per_unit": discount,
                "net_unit_price": net_price,
                "unit_variable_cost": product["unit_cost"],
                "ordered_net_sales": ordered_sales,
                "scenario_id": config.scenario_id,
                "dataset_build_id": build_id,
                "is_synthetic": True,
            }
            line_rows.append(row)
            internal_lines.append(
                {
                    **row,
                    "weight_kg": product["weight_kg"],
                    "volume_m3": product["volume_m3"],
                }
            )

        order_specs.append(
            {
                "order_number": order_number,
                "order_id": order_id,
                "customer_id": draft["customer_id"],
                "customer": customer,
                "service_class": service_class,
                "order_datetime": draft["order_datetime"],
                "promised_datetime": draft["promised_datetime"],
                "lines": internal_lines,
            }
        )

    return order_rows, line_rows, order_specs


def _generate_inventory(
    config: ScenarioConfig,
    build_id: str,
    product_specs: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    days = (config.period_end - config.period_start).days + 1
    for day_index in range(days):
        snapshot_date = config.period_start + timedelta(days=day_index)
        for sku_index, sku_id in enumerate(product_specs, start=1):
            safety_stock = 20 + (sku_index % 10) * 3
            reorder_point = safety_stock * 2
            state = (day_index * 13 + sku_index * 7) % 100
            if state < 2:
                available = 0
            elif state < 12:
                available = 1 + ((day_index + sku_index) % reorder_point)
            else:
                available = reorder_point + 10 + ((day_index * sku_index) % 120)
            allocated = (day_index + sku_index * 3) % 25
            on_hand = available + allocated
            rows.append(
                {
                    "snapshot_date": snapshot_date.isoformat(),
                    "site_id": _SITE_ID,
                    "sku_id": sku_id,
                    "on_hand_quantity": on_hand,
                    "allocated_quantity": allocated,
                    "available_quantity": available,
                    "safety_stock_quantity": safety_stock,
                    "reorder_point_quantity": reorder_point,
                    "is_stockout": available == 0,
                    "is_low_inventory": 0 < available <= reorder_point,
                    "scenario_id": config.scenario_id,
                    "dataset_build_id": build_id,
                    "is_synthetic": True,
                }
            )
    return rows


def _generate_deliveries_and_costs(
    config: ScenarioConfig,
    build_id: str,
    order_specs: list[dict[str, Any]],
    vehicle_specs: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    delivery_rows: list[dict[str, Any]] = []
    delivery_line_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    vehicle_ids = list(vehicle_specs)
    delivery_number = 0
    delivery_line_number = 0
    cost_number = 0

    def append_cost(
        *,
        order_id: str,
        delivery_id: str | None,
        activity_datetime: datetime,
        cost_type: str,
        amount: Decimal,
        driver_value: float | int,
        driver_unit: str,
        allocation_method: str,
    ) -> None:
        nonlocal cost_number
        cost_number += 1
        cost_rows.append(
            {
                "cost_activity_id": f"CST-SYN-{cost_number:08d}",
                "order_id": order_id,
                "delivery_id": delivery_id,
                "activity_datetime": _iso(activity_datetime),
                "cost_type": cost_type,
                "cost_amount": _money(amount),
                "currency_code": config.currency,
                "cost_driver_value": round(float(driver_value), 3),
                "cost_driver_unit": driver_unit,
                "allocation_method": allocation_method,
                "scenario_id": config.scenario_id,
                "dataset_build_id": build_id,
                "is_synthetic": True,
            }
        )

    for order in order_specs:
        service_class = order["service_class"]
        is_complete = service_class.startswith("complete")
        is_on_time = service_class.endswith("on_time")
        event_count = 2 if order["order_number"] % 4 == 0 else 1

        if is_on_time:
            final_time = order["promised_datetime"] - timedelta(hours=2)
            event_times = (
                [final_time]
                if event_count == 1
                else [final_time - timedelta(hours=10), final_time]
            )
        else:
            first_late = order["promised_datetime"] + timedelta(hours=4)
            event_times = (
                [first_late + timedelta(hours=8)]
                if event_count == 1
                else [first_late, first_late + timedelta(hours=14)]
            )

        delivery_specs: list[dict[str, Any]] = []
        customer = order["customer"]
        base_distance = _haversine_km(
            _SITE_LATITUDE,
            _SITE_LONGITUDE,
            customer["latitude"],
            customer["longitude"],
        )
        distance_km = round(base_distance * 1.18, 3)

        for sequence, delivery_datetime in enumerate(event_times, start=1):
            delivery_number += 1
            delivery_id = f"DEL-SYN-{delivery_number:06d}"
            vehicle_id = vehicle_ids[(order["order_number"] + sequence - 2) % len(vehicle_ids)]
            incident_divisor = 17 if customer["high_cts"] else 97
            has_incident = (order["order_number"] + sequence) % incident_divisor == 0
            delivery_status = (
                "delivered_with_incident" if has_incident else "delivered"
            )
            dispatch_datetime = delivery_datetime - timedelta(hours=3)
            if dispatch_datetime < order["order_datetime"]:
                dispatch_datetime = order["order_datetime"]
            delivery_rows.append(
                {
                    "delivery_id": delivery_id,
                    "order_id": order["order_id"],
                    "vehicle_id": vehicle_id,
                    "origin_site_id": _SITE_ID,
                    "destination_location_id": customer["location_id"],
                    "delivery_sequence": sequence,
                    "dispatch_datetime": _iso(dispatch_datetime),
                    "delivery_datetime": _iso(delivery_datetime),
                    "distance_km": distance_km,
                    "delivery_status": delivery_status,
                    "scenario_id": config.scenario_id,
                    "dataset_build_id": build_id,
                    "is_synthetic": True,
                }
            )
            delivery_specs.append(
                {
                    "delivery_id": delivery_id,
                    "vehicle_id": vehicle_id,
                    "delivery_datetime": delivery_datetime,
                    "distance_km": distance_km,
                    "has_incident": has_incident,
                    "delivered_quantity": 0,
                    "delivered_weight_kg": 0.0,
                    "delivered_volume_m3": 0.0,
                }
            )

        for line_index, line in enumerate(order["lines"]):
            ordered_quantity = int(line["ordered_quantity"])
            delivered_total = (
                ordered_quantity
                if is_complete
                else max(1, int(math.floor(ordered_quantity * 0.65)))
            )
            if event_count == 1:
                allocations = [delivered_total]
            elif delivered_total == 1:
                allocations = [1, 0] if line_index % 2 == 0 else [0, 1]
            else:
                first_quantity = max(1, delivered_total // 2)
                allocations = [first_quantity, delivered_total - first_quantity]

            for event_index, quantity in enumerate(allocations):
                if quantity == 0:
                    continue
                delivery_line_number += 1
                delivery = delivery_specs[event_index]
                delivery_line_rows.append(
                    {
                        "delivery_line_id": f"DLN-SYN-{delivery_line_number:07d}",
                        "delivery_id": delivery["delivery_id"],
                        "order_line_id": line["order_line_id"],
                        "delivered_quantity": quantity,
                        "scenario_id": config.scenario_id,
                        "dataset_build_id": build_id,
                        "is_synthetic": True,
                    }
                )
                delivery["delivered_quantity"] += quantity
                delivery["delivered_weight_kg"] += quantity * line["weight_kg"]
                delivery["delivered_volume_m3"] += quantity * line["volume_m3"]

        for delivery in delivery_specs:
            vehicle = vehicle_specs[delivery["vehicle_id"]]
            if delivery["delivered_weight_kg"] > vehicle["capacity_kg"]:
                raise RuntimeError("generated delivery exceeds vehicle weight capacity")
            if delivery["delivered_volume_m3"] > vehicle["capacity_m3"]:
                raise RuntimeError("generated delivery exceeds vehicle volume capacity")

        delivered_units = sum(item["delivered_quantity"] for item in delivery_specs)
        delivered_weight = sum(item["delivered_weight_kg"] for item in delivery_specs)
        multiplier = Decimal("8.0") if customer["high_cts"] else Decimal("0.5")
        base_time = order["order_datetime"]
        append_cost(
            order_id=order["order_id"],
            delivery_id=None,
            activity_datetime=base_time + timedelta(minutes=30),
            cost_type="order_processing",
            amount=Decimal("1200") * multiplier,
            driver_value=1,
            driver_unit="order",
            allocation_method="direct_order",
        )
        append_cost(
            order_id=order["order_id"],
            delivery_id=None,
            activity_datetime=base_time + timedelta(minutes=60),
            cost_type="picking",
            amount=Decimal(delivered_units) * Decimal("60") * multiplier,
            driver_value=delivered_units,
            driver_unit="unit",
            allocation_method="direct_order",
        )
        append_cost(
            order_id=order["order_id"],
            delivery_id=None,
            activity_datetime=base_time + timedelta(minutes=90),
            cost_type="handling",
            amount=Decimal(str(delivered_weight)) * Decimal("18") * multiplier,
            driver_value=delivered_weight,
            driver_unit="kg",
            allocation_method="proportional_weight",
        )

        for delivery in delivery_specs:
            vehicle = vehicle_specs[delivery["vehicle_id"]]
            append_cost(
                order_id=order["order_id"],
                delivery_id=delivery["delivery_id"],
                activity_datetime=delivery["delivery_datetime"],
                cost_type="transport",
                amount=(
                    Decimal(str(delivery["distance_km"]))
                    * vehicle["variable_cost_km"]
                    * multiplier
                ),
                driver_value=delivery["distance_km"],
                driver_unit="km",
                allocation_method="proportional_distance",
            )
            append_cost(
                order_id=order["order_id"],
                delivery_id=delivery["delivery_id"],
                activity_datetime=delivery["delivery_datetime"],
                cost_type="delivery",
                amount=Decimal("3000") * multiplier,
                driver_value=1,
                driver_unit="stop",
                allocation_method="direct_delivery",
            )
            if delivery["has_incident"]:
                append_cost(
                    order_id=order["order_id"],
                    delivery_id=delivery["delivery_id"],
                    activity_datetime=delivery["delivery_datetime"],
                    cost_type="incident",
                    amount=Decimal("12000") * multiplier,
                    driver_value=1,
                    driver_unit="incident",
                    allocation_method="direct_delivery",
                )

    return delivery_rows, delivery_line_rows, cost_rows


def generate_synthetic_data(config: ScenarioConfig) -> GeneratedSyntheticData:
    """Generate all contract datasets in memory from one validated configuration."""

    build_id = _build_id(config)
    rng = np.random.default_rng(config.seed)
    master_rows, context = _generate_master_rows(config, rng, build_id)
    order_rows, line_rows, order_specs = _generate_orders_and_lines(
        config,
        rng,
        build_id,
        context["customer_specs"],
        context["product_specs"],
    )
    delivery_rows, delivery_line_rows, cost_rows = _generate_deliveries_and_costs(
        config,
        build_id,
        order_specs,
        context["vehicle_specs"],
    )
    inventory_rows = _generate_inventory(
        config,
        build_id,
        context["product_specs"],
    )

    all_rows: dict[str, list[dict[str, Any]]] = {
        **master_rows,
        "orders": order_rows,
        "order_lines": line_rows,
        "inventory": inventory_rows,
        "deliveries": delivery_rows,
        "delivery_lines": delivery_line_rows,
        "cost_activities": cost_rows,
    }
    tables = {
        name: pd.DataFrame(all_rows[name], columns=DATASET_COLUMNS[name])
        for name in DATASET_ORDER
    }
    return GeneratedSyntheticData(dataset_build_id=build_id, tables=tables)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def publish_synthetic_csvs(
    generated: GeneratedSyntheticData,
    output_dir: str | Path,
) -> dict[str, str]:
    """Atomically publish deterministic UTF-8 CSV files and return their hashes."""

    output = Path(output_dir).resolve()
    if output == output.parent:
        raise ValueError("output_dir cannot be a filesystem root")
    output.parent.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex
    staging = output.parent / f".{output.name}.staging-{token}"
    backup = output.parent / f".{output.name}.backup-{token}"
    staging.mkdir(parents=False, exist_ok=False)

    def replace_with_retry(source: Path, target: Path) -> None:
        for attempt in range(20):
            try:
                os.replace(source, target)
                return
            except PermissionError:
                if attempt == 19:
                    raise
                sleep(min(0.1 * (attempt + 1), 0.5))

    hashes: dict[str, str] = {}
    try:
        for name in DATASET_ORDER:
            path = staging / f"{name}.csv"
            generated.tables[name].to_csv(
                path,
                index=False,
                encoding="utf-8",
                lineterminator="\n",
            )
            hashes[name] = _file_sha256(path)

        had_previous = output.exists()
        if had_previous:
            replace_with_retry(output, backup)
        try:
            replace_with_retry(staging, output)
        except Exception:
            if had_previous and backup.exists() and not output.exists():
                replace_with_retry(backup, output)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if backup.exists():
            shutil.rmtree(backup)

    return hashes
