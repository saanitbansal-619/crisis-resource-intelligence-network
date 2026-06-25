"""Tests for the OR-Tools optimization engine.

The optimizer's core function operates on in-memory records, so most tests
run without a database. Tests skip gracefully when OR-Tools is not installed.
"""

import pytest

from analytics import optimization_engine
from analytics.optimization_engine import (
    ORTOOLS_AVAILABLE,
    generate_optimized_transfers,
)

REQUIRED_RECOMMENDATION_FIELDS = {
    "source_zone_name",
    "destination_zone_name",
    "resource_type",
    "optimized_quantity",
    "simulated_transport_cost",
    "match_type",
    "confidence",
}


def _shortage(zone_id: str, zone_name: str, country: str, resource_type: str, gap: int) -> dict:
    return {
        "zone_id": zone_id,
        "zone_name": zone_name,
        "country": country,
        "resource_type": resource_type,
        "shortage_gap": gap,
        "latitude": None,
        "longitude": None,
    }


def _surplus(zone_id: str, zone_name: str, country: str, resource_type: str, amount: int) -> dict:
    return {
        "zone_id": zone_id,
        "zone_name": zone_name,
        "country": country,
        "resource_type": resource_type,
        "surplus_amount": amount,
        "latitude": None,
        "longitude": None,
    }


@pytest.fixture
def sample_result() -> dict:
    if not ORTOOLS_AVAILABLE:
        pytest.skip("OR-Tools is not installed; optimization tests skipped.")
    shortages = [
        _shortage("D1", "Demand One", "CountryA", "water_kits", 300),
        _shortage("D2", "Demand Two", "CountryB", "food_kits", 150),
    ]
    surpluses = [
        _surplus("S1", "Supply One", "CountryA", "water_kits", 500),
        _surplus("S2", "Supply Two", "CountryB", "food_kits", 400),
    ]
    return generate_optimized_transfers(shortages, surpluses)


def test_optimization_module_imports() -> None:
    assert hasattr(optimization_engine, "generate_optimized_transfers")
    assert hasattr(optimization_engine, "generate_optimized_transfers_from_mismatches")


def test_result_is_dict_like(sample_result: dict) -> None:
    assert isinstance(sample_result, dict)


def test_result_contains_optimization_status(sample_result: dict) -> None:
    assert "optimization_status" in sample_result
    assert isinstance(sample_result["optimization_status"], str)


def test_result_contains_recommendations_list(sample_result: dict) -> None:
    assert "recommendations" in sample_result
    assert isinstance(sample_result["recommendations"], list)


def test_total_quantity_moved_non_negative(sample_result: dict) -> None:
    assert sample_result.get("total_quantity_moved", 0) >= 0


def test_total_simulated_transport_cost_non_negative(sample_result: dict) -> None:
    assert sample_result.get("total_simulated_transport_cost", 0) >= 0


def test_recommendations_have_required_fields(sample_result: dict) -> None:
    recommendations = sample_result["recommendations"]
    assert recommendations, "Expected at least one optimized transfer for the sample problem"
    for item in recommendations:
        missing = REQUIRED_RECOMMENDATION_FIELDS - set(item)
        assert not missing, f"Recommendation missing fields: {missing}"


def test_no_negative_optimized_quantity(sample_result: dict) -> None:
    for item in sample_result["recommendations"]:
        assert item["optimized_quantity"] >= 0


def test_costs_are_labeled_simulated_not_usd(sample_result: dict) -> None:
    cost_note = (sample_result.get("cost_note") or "").lower()
    assert cost_note, "Expected a cost_note describing simulated cost units"
    assert "simulated" in cost_note
    assert "relative cost units" in cost_note
    assert "not real-world usd" in cost_note


def test_recommendations_expose_simulated_cost_fields(sample_result: dict) -> None:
    for item in sample_result["recommendations"]:
        assert "simulated_transport_cost" in item
        assert "simulated_unit_cost" in item


def test_missing_ortools_returns_graceful_status() -> None:
    """If OR-Tools is unavailable, the engine returns an 'unavailable' status."""
    if ORTOOLS_AVAILABLE:
        pytest.skip("OR-Tools is installed; graceful-unavailable path not exercised.")
    result = generate_optimized_transfers(
        [_shortage("D1", "Demand", "CountryA", "water_kits", 100)],
        [_surplus("S1", "Supply", "CountryA", "water_kits", 200)],
    )
    assert result["optimization_status"] == "unavailable"
    assert result["recommendations"] == []
