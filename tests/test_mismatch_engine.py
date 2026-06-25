"""Pure-function tests for the supply-demand mismatch engine.

These tests operate on in-memory DataFrames and do not touch the database.
"""

import pandas as pd
import pytest

from analytics.mismatch_engine import (
    URGENCY_WEIGHTS,
    calculate_mismatches,
    classify_status,
)


def _inventory(zone_id: str, resource_type: str, available: int) -> dict:
    return {
        "zone_id": zone_id,
        "resource_type": resource_type,
        "quantity_available": available,
    }


def _request(zone_id: str, resource_type: str, needed: int, urgency: str) -> dict:
    return {
        "zone_id": zone_id,
        "resource_type": resource_type,
        "quantity_needed": needed,
        "urgency_level": urgency,
    }


def _row_for(df: pd.DataFrame, zone_id: str, resource_type: str) -> pd.Series:
    match = df[(df["zone_id"] == zone_id) & (df["resource_type"] == resource_type)]
    assert not match.empty, f"No mismatch row for {zone_id}/{resource_type}"
    return match.iloc[0]


def test_shortage_gap_positive_when_demand_exceeds_supply() -> None:
    inventory = pd.DataFrame([_inventory("Z1", "water_kits", 100)])
    requests = pd.DataFrame([_request("Z1", "water_kits", 400, "high")])

    result = calculate_mismatches(inventory, requests)
    row = _row_for(result, "Z1", "water_kits")

    assert row["shortage_gap"] == 300
    assert "shortage" in row["status_label"]


def test_surplus_status_when_supply_exceeds_demand() -> None:
    inventory = pd.DataFrame([_inventory("Z2", "food_kits", 1000)])
    requests = pd.DataFrame([_request("Z2", "food_kits", 100, "low")])

    result = calculate_mismatches(inventory, requests)
    row = _row_for(result, "Z2", "food_kits")

    assert row["shortage_gap"] < 0
    assert row["status_label"] == "surplus"


def test_stable_status_when_supply_meets_demand() -> None:
    inventory = pd.DataFrame([_inventory("Z3", "blankets", 500)])
    requests = pd.DataFrame([_request("Z3", "blankets", 500, "medium")])

    result = calculate_mismatches(inventory, requests)
    row = _row_for(result, "Z3", "blankets")

    assert row["shortage_gap"] == 0
    assert row["status_label"] == "stable"


def test_urgency_weighting_increases_mismatch_score() -> None:
    inventory = pd.DataFrame(
        [_inventory("ZA", "medicine", 100), _inventory("ZB", "medicine", 100)]
    )
    requests = pd.DataFrame(
        [
            _request("ZA", "medicine", 300, "low"),
            _request("ZB", "medicine", 300, "critical"),
        ]
    )

    result = calculate_mismatches(inventory, requests)
    low_score = _row_for(result, "ZA", "medicine")["mismatch_score"]
    critical_score = _row_for(result, "ZB", "medicine")["mismatch_score"]

    assert critical_score > low_score


def test_classify_status_boundaries() -> None:
    assert classify_status(-150, -0.5) == "surplus"
    assert classify_status(0, 0.0) == "stable"
    assert classify_status(10, 0.10) == "moderate shortage"
    assert classify_status(100, 0.40) == "severe shortage"
    assert classify_status(500, 0.90) == "critical shortage"


def test_urgency_weights_are_monotonic() -> None:
    assert URGENCY_WEIGHTS["low"] < URGENCY_WEIGHTS["medium"]
    assert URGENCY_WEIGHTS["medium"] < URGENCY_WEIGHTS["high"]
    assert URGENCY_WEIGHTS["high"] < URGENCY_WEIGHTS["critical"]
