"""Pure-function tests for the deterministic reallocation engine.

These tests build mismatch rows in memory and do not touch the database.
"""

from analytics.reallocation_engine import (
    _match_metadata,
    build_shortage_records,
    build_surplus_records,
    generate_recommendations_from_mismatches,
    generate_reallocation_recommendations,
)


def _mismatch_row(
    zone_id: str,
    zone_name: str,
    country: str,
    resource_type: str,
    status_label: str,
    shortage_gap: int,
    total_available: int = 0,
    total_needed: int = 0,
    urgency_level: str = "high",
    mismatch_score: float = 100.0,
) -> dict:
    return {
        "zone_id": zone_id,
        "zone_name": zone_name,
        "country": country,
        "resource_type": resource_type,
        "status_label": status_label,
        "shortage_gap": shortage_gap,
        "total_available": total_available,
        "total_needed": total_needed,
        "urgency_level": urgency_level,
        "mismatch_score": mismatch_score,
    }


def test_same_country_confidence_higher_than_cross_country() -> None:
    same_confidence, _ = _match_metadata("same_country")
    cross_confidence, _ = _match_metadata("cross_country")

    assert same_confidence == "high"
    assert cross_confidence == "low"


def test_resource_types_must_match_before_transfer() -> None:
    rows = [
        _mismatch_row("Z1", "Demand Zone", "CountryA", "water_kits", "critical shortage", 200),
        _mismatch_row(
            "Z2", "Supply Zone", "CountryA", "food_kits", "surplus", -500, total_available=500
        ),
    ]
    shortages = build_shortage_records(rows)
    surpluses = build_surplus_records(rows)
    recommendations = generate_reallocation_recommendations(shortages, surpluses)

    assert recommendations == [], "Different resource types should not be matched"


def test_matching_resource_types_generate_transfer() -> None:
    rows = [
        _mismatch_row("Z1", "Demand Zone", "CountryA", "water_kits", "critical shortage", 200),
        _mismatch_row(
            "Z2", "Supply Zone", "CountryA", "water_kits", "surplus", -500, total_available=500
        ),
    ]
    result = generate_recommendations_from_mismatches(rows)
    recommendations = result["recommendations"]

    assert len(recommendations) >= 1
    transfer = recommendations[0]
    assert transfer["resource_type"] == "water_kits"
    assert transfer["from_zone_id"] == "Z2"
    assert transfer["to_zone_id"] == "Z1"
    assert transfer["recommended_quantity"] > 0


def test_same_country_match_preferred_and_high_confidence() -> None:
    rows = [
        _mismatch_row("Z1", "Demand Zone", "CountryA", "water_kits", "critical shortage", 200),
        _mismatch_row(
            "Z2", "Same Country Supply", "CountryA", "water_kits", "surplus", -500, total_available=500
        ),
    ]
    result = generate_recommendations_from_mismatches(rows)
    transfer = result["recommendations"][0]

    assert transfer["match_type"] == "same_country"
    assert transfer["confidence_level"] == "high"


def test_cross_country_fallback_labeled_low_confidence() -> None:
    rows = [
        _mismatch_row("Z1", "Demand Zone", "CountryA", "water_kits", "critical shortage", 200),
        _mismatch_row(
            "Z2", "Cross Border Supply", "CountryB", "water_kits", "surplus", -500, total_available=500
        ),
    ]
    result = generate_recommendations_from_mismatches(rows)
    transfer = result["recommendations"][0]

    assert transfer["match_type"] == "cross_country_fallback"
    assert transfer["confidence_level"] == "low"


def test_recommended_quantity_never_exceeds_shortage_gap() -> None:
    rows = [
        _mismatch_row("Z1", "Demand Zone", "CountryA", "water_kits", "critical shortage", 100),
        _mismatch_row(
            "Z2", "Supply Zone", "CountryA", "water_kits", "surplus", -900, total_available=900
        ),
    ]
    result = generate_recommendations_from_mismatches(rows)
    total_transferred = sum(item["recommended_quantity"] for item in result["recommendations"])

    assert total_transferred <= 100
