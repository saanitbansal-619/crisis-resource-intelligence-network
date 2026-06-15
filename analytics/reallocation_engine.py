"""
Resource reallocation recommendation engine.

Matches surplus zones to shortage zones by resource type, preferring same-country
transfers and allocating by shortage priority.

Run: python -m analytics.reallocation_engine
"""

from __future__ import annotations

SHORTAGE_STATUSES = frozenset(
    {"moderate shortage", "severe shortage", "critical shortage"}
)
SURPLUS_STATUS = "surplus"

STATUS_PRIORITY = {
    "critical shortage": 0,
    "severe shortage": 1,
    "moderate shortage": 2,
}

URGENCY_PRIORITY = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}

MATCH_TYPE_PRIORITY = {
    "same_country": 0,
    "cross_country_fallback": 1,
}

SAME_COUNTRY_FEASIBILITY_NOTE = (
    "Same-country transfer candidate. Validate transport capacity, field access, "
    "and partner availability before dispatch."
)
CROSS_COUNTRY_FEASIBILITY_NOTE = (
    "Cross-country fallback candidate. Requires customs, transport planning, partner "
    "approval, and field validation before use."
)

METHOD_NOTE = (
    "Recommendations are generated from simulated resource inventory, requests, "
    "and mismatch scores."
)


def _format_resource_label(resource_type: str) -> str:
    if not resource_type:
        return "resource"
    return str(resource_type).replace("_", " ").title()


def _clean_status(status: str | None) -> str:
    return (status or "").strip().lower()


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_shortage_records(mismatch_rows: list[dict]) -> list[dict]:
    """Extract and normalize shortage records from mismatch score rows."""
    shortages: list[dict] = []
    for row in mismatch_rows:
        status = _clean_status(row.get("status_label") or row.get("status"))
        if status not in SHORTAGE_STATUSES:
            continue

        shortage_gap = _to_int(row.get("shortage_gap"))
        if shortage_gap <= 0:
            continue

        shortages.append(
            {
                "zone_id": row.get("zone_id"),
                "zone_name": row.get("zone_name") or row.get("zone_id") or "Unknown Zone",
                "country": row.get("country") or "—",
                "resource_type": row.get("resource_type"),
                "total_available": _to_int(row.get("total_available")),
                "total_needed": _to_int(row.get("total_needed")),
                "shortage_gap": shortage_gap,
                "urgency_level": row.get("urgency_level") or "—",
                "mismatch_score": _to_float(row.get("mismatch_score")),
                "status": status,
            }
        )

    shortages.sort(
        key=lambda item: (
            STATUS_PRIORITY.get(item["status"], 99),
            -item["mismatch_score"],
            -item["shortage_gap"],
        )
    )
    return shortages


def build_surplus_records(mismatch_rows: list[dict]) -> list[dict]:
    """Extract and normalize surplus records from mismatch score rows."""
    surpluses: list[dict] = []
    for row in mismatch_rows:
        status = _clean_status(row.get("status_label") or row.get("status"))
        if status != SURPLUS_STATUS:
            continue

        shortage_gap = _to_int(row.get("shortage_gap"))
        surplus_amount = abs(shortage_gap) if shortage_gap < 0 else 0
        if surplus_amount <= 0:
            surplus_amount = max(
                0,
                _to_int(row.get("total_available")) - _to_int(row.get("total_needed")),
            )
        if surplus_amount <= 0:
            continue

        surpluses.append(
            {
                "zone_id": row.get("zone_id"),
                "zone_name": row.get("zone_name") or row.get("zone_id") or "Unknown Zone",
                "country": row.get("country") or "—",
                "resource_type": row.get("resource_type"),
                "surplus_amount": surplus_amount,
                "available_amount": _to_int(row.get("total_available")),
                "status": status,
            }
        )
    return surpluses


def _build_reason(
    to_zone_name: str,
    from_zone_name: str,
    resource_type: str,
    status: str,
) -> str:
    resource_label = _format_resource_label(resource_type)
    urgency_phrase = status.replace(" shortage", "") if "shortage" in status else status
    return (
        f"{to_zone_name} has a {urgency_phrase} {resource_label} shortage, "
        f"while {from_zone_name} has available {resource_label} surplus."
    )


def _match_metadata(match_type: str) -> tuple[str, str]:
    if match_type == "same_country":
        return "high", SAME_COUNTRY_FEASIBILITY_NOTE
    return "low", CROSS_COUNTRY_FEASIBILITY_NOTE


def sort_recommendations(recommendations: list[dict]) -> list[dict]:
    """Sort recommendations for operational review: same-country and urgency first."""
    return sorted(
        recommendations,
        key=lambda item: (
            MATCH_TYPE_PRIORITY.get(item.get("match_type"), 99),
            URGENCY_PRIORITY.get((item.get("urgency_level") or "").strip().lower(), 99),
            -_to_float(item.get("priority_score")),
            -_to_int(item.get("recommended_quantity")),
        ),
    )


def generate_reallocation_recommendations(
    shortage_records: list[dict],
    surplus_records: list[dict],
) -> list[dict]:
    """
    Match shortages to surplus pools deterministically.

    Shortages are processed in priority order. Surplus is consumed per source zone
    and resource type without exceeding available amounts.
    """
    remaining_gap: dict[tuple[str, str], int] = {}
    for shortage in shortage_records:
        key = (shortage["zone_id"], shortage["resource_type"])
        remaining_gap[key] = shortage["shortage_gap"]

    surplus_pool: dict[tuple[str, str], int] = {}
    surplus_lookup: dict[tuple[str, str], dict] = {}
    for surplus in surplus_records:
        key = (surplus["zone_id"], surplus["resource_type"])
        surplus_pool[key] = surplus["surplus_amount"]
        surplus_lookup[key] = surplus

    recommendations: list[dict] = []

    for shortage in shortage_records:
        dest_key = (shortage["zone_id"], shortage["resource_type"])
        gap_remaining = remaining_gap.get(dest_key, 0)
        if gap_remaining <= 0:
            continue

        resource_type = shortage["resource_type"]
        dest_zone_id = shortage["zone_id"]
        dest_country = (shortage.get("country") or "").strip().lower()

        candidates: list[tuple[int, int, dict]] = []
        for pool_key, available in surplus_pool.items():
            source_zone_id, candidate_resource = pool_key
            if candidate_resource != resource_type:
                continue
            if source_zone_id == dest_zone_id:
                continue
            if available <= 0:
                continue

            source = surplus_lookup[pool_key]
            source_country = (source.get("country") or "").strip().lower()
            same_country = bool(dest_country and source_country and dest_country == source_country)
            country_rank = 0 if same_country else 1
            candidates.append((country_rank, -available, source))

        candidates.sort(key=lambda item: (item[0], item[1]))

        for country_rank, _, source in candidates:
            gap_remaining = remaining_gap.get(dest_key, 0)
            if gap_remaining <= 0:
                break

            pool_key = (source["zone_id"], resource_type)
            available = surplus_pool.get(pool_key, 0)
            if available <= 0:
                continue

            recommended_quantity = min(gap_remaining, available)
            if recommended_quantity <= 0:
                continue

            match_type = "same_country" if country_rank == 0 else "cross_country_fallback"
            confidence_level, feasibility_note = _match_metadata(match_type)
            remaining_after = gap_remaining - recommended_quantity

            recommendations.append(
                {
                    "resource_type": resource_type,
                    "from_zone_id": source["zone_id"],
                    "from_zone_name": source["zone_name"],
                    "from_country": source["country"],
                    "to_zone_id": shortage["zone_id"],
                    "to_zone_name": shortage["zone_name"],
                    "to_country": shortage["country"],
                    "recommended_quantity": recommended_quantity,
                    "remaining_gap_after_transfer": remaining_after,
                    "urgency_level": shortage["urgency_level"],
                    "priority_score": shortage["mismatch_score"],
                    "match_type": match_type,
                    "confidence_level": confidence_level,
                    "feasibility_note": feasibility_note,
                    "reason": _build_reason(
                        shortage["zone_name"],
                        source["zone_name"],
                        resource_type,
                        shortage["status"],
                    ),
                }
            )

            surplus_pool[pool_key] = available - recommended_quantity
            remaining_gap[dest_key] = remaining_after

    return sort_recommendations(recommendations)


def generate_recommendations_from_mismatches(mismatch_rows: list[dict]) -> dict:
    """Build the API response payload from raw mismatch score rows."""
    shortages = build_shortage_records(mismatch_rows)
    surpluses = build_surplus_records(mismatch_rows)
    recommendations = generate_reallocation_recommendations(shortages, surpluses)
    return {
        "recommendations": recommendations,
        "total_recommendations": len(recommendations),
        "method_note": METHOD_NOTE,
    }


def main() -> None:
    import os
    import sys
    from pathlib import Path

    from dotenv import load_dotenv
    from sqlalchemy import create_engine, text

    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"
    load_dotenv(dotenv_path=env_path, override=True, encoding="utf-8-sig")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not found.")
        sys.exit(1)

    query = """
        SELECT
            m.zone_id,
            z.zone_name,
            z.country,
            m.resource_type,
            m.total_available,
            m.total_needed,
            m.shortage_gap,
            m.urgency_level,
            m.mismatch_score,
            m.status_label
        FROM mismatch_scores m
        JOIN zones z ON m.zone_id = z.zone_id
        ORDER BY m.mismatch_score DESC
    """
    engine = create_engine(database_url)
    with engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(text(query)).mappings()]

    result = generate_recommendations_from_mismatches(rows)
    print(f"Total recommendations: {result['total_recommendations']}")
    for index, item in enumerate(result["recommendations"][:10], start=1):
        print("-" * 72)
        print(f"{index}. {_format_resource_label(item['resource_type'])}")
        print(f"   {item['from_zone_name']} ({item['from_country']}) -> {item['to_zone_name']} ({item['to_country']})")
        print(f"   Quantity: {item['recommended_quantity']} | Match: {item['match_type']}")
        print(f"   Confidence: {item.get('confidence_level')} | {item.get('feasibility_note')}")
        print(f"   {item['reason']}")


if __name__ == "__main__":
    main()
