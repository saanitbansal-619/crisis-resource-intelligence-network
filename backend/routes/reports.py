"""
Summary report endpoints for KPIs and resource analytics.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import get_db, row_to_dict, rows_to_dicts

URGENCY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def _normalize_crisis_event_id(event_id: str | None) -> str | None:
    """Strip trailing '.0' so values like '1544854.0' match GDACS alert_id '1544854'."""
    if not event_id:
        return None
    normalized = event_id.strip()
    if normalized.endswith(".0"):
        normalized = normalized[:-2]
    return normalized or None


def _most_urgent_level(needs: list[dict]) -> str | None:
    """Return the highest urgency level across priority needs."""
    best_level = None
    best_rank = 0
    for row in needs:
        level = row.get("urgency_level")
        if level and URGENCY_RANK.get(level, 0) > best_rank:
            best_rank = URGENCY_RANK[level]
            best_level = level
    return best_level


router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/overview")
def get_overview(db: Session = Depends(get_db)) -> dict:
    """Return high-level system KPIs."""
    result = db.execute(
        text(
            """
            SELECT
                (SELECT COUNT(*) FROM zones) AS total_zones,
                (SELECT COUNT(*) FROM organizations) AS total_organizations,
                (SELECT COUNT(*) FROM resource_inventory) AS total_inventory_records,
                (SELECT COUNT(*) FROM resource_requests) AS total_request_records,
                (SELECT COUNT(*) FROM mismatch_scores) AS total_mismatch_records,
                (SELECT COUNT(*) FROM mismatch_scores WHERE status_label = 'critical shortage')
                    AS critical_shortage_count,
                (SELECT COUNT(*) FROM mismatch_scores WHERE status_label = 'severe shortage')
                    AS severe_shortage_count,
                (SELECT COUNT(*) FROM mismatch_scores WHERE status_label = 'surplus')
                    AS surplus_count,
                (SELECT COUNT(*) FROM crisis_reports) AS total_crisis_reports,
                (SELECT COUNT(*) FROM gdacs_alerts) AS total_gdacs_alerts
            """
        )
    )
    overview = row_to_dict(result)
    return overview or {}


@router.get("/resource-summary")
def get_resource_summary(db: Session = Depends(get_db)) -> list[dict]:
    """Return grouped resource mismatch summary by resource type."""
    result = db.execute(
        text(
            """
            SELECT
                resource_type,
                SUM(total_available) AS total_available,
                SUM(total_needed) AS total_needed,
                SUM(shortage_gap) AS total_shortage_gap,
                COUNT(*) AS number_of_zones,
                COUNT(*) FILTER (WHERE status_label = 'critical shortage')
                    AS critical_shortage_count,
                COUNT(*) FILTER (WHERE status_label = 'severe shortage')
                    AS severe_shortage_count,
                COUNT(*) FILTER (WHERE status_label = 'surplus') AS surplus_count
            FROM mismatch_scores
            GROUP BY resource_type
            ORDER BY total_shortage_gap DESC
            """
        )
    )
    return rows_to_dicts(result)


@router.get("/zone-briefing/{zone_id}")
def get_zone_briefing(zone_id: str, db: Session = Depends(get_db)) -> dict:
    """Return a consolidated briefing for one crisis zone."""
    zone = row_to_dict(
        db.execute(
            text(
                """
                SELECT
                    zone_id,
                    zone_name,
                    country,
                    admin_region,
                    latitude,
                    longitude,
                    population_estimate,
                    crisis_event_id
                FROM zones
                WHERE zone_id = :zone_id
                """
            ),
            {"zone_id": zone_id},
        )
    )
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found")

    priority_needs = rows_to_dicts(
        db.execute(
            text(
                """
                SELECT
                    resource_type,
                    total_available,
                    total_needed,
                    shortage_gap,
                    shortage_ratio,
                    urgency_level,
                    mismatch_score,
                    status_label
                FROM mismatch_scores
                WHERE zone_id = :zone_id
                  AND status_label IN (
                      'critical shortage',
                      'severe shortage',
                      'moderate shortage'
                  )
                ORDER BY mismatch_score DESC
                """
            ),
            {"zone_id": zone_id},
        )
    )

    available_surplus = rows_to_dicts(
        db.execute(
            text(
                """
                SELECT
                    resource_type,
                    total_available,
                    total_needed,
                    shortage_gap,
                    status_label
                FROM mismatch_scores
                WHERE zone_id = :zone_id
                  AND status_label = 'surplus'
                ORDER BY shortage_gap ASC
                """
            ),
            {"zone_id": zone_id},
        )
    )

    inventory = rows_to_dicts(
        db.execute(
            text(
                """
                SELECT
                    ri.resource_type,
                    ri.quantity_available,
                    ri.unit,
                    o.org_name,
                    o.org_type,
                    ri.last_updated
                FROM resource_inventory ri
                JOIN organizations o ON ri.org_id = o.org_id
                WHERE ri.zone_id = :zone_id
                ORDER BY ri.resource_type, o.org_name
                """
            ),
            {"zone_id": zone_id},
        )
    )

    requests = rows_to_dicts(
        db.execute(
            text(
                """
                SELECT
                    resource_type,
                    quantity_needed,
                    urgency_level,
                    requested_by,
                    request_timestamp
                FROM resource_requests
                WHERE zone_id = :zone_id
                ORDER BY request_timestamp DESC
                """
            ),
            {"zone_id": zone_id},
        )
    )

    related_alert = None
    normalized_event_id = _normalize_crisis_event_id(zone.get("crisis_event_id"))
    if normalized_event_id:
        related_alert = row_to_dict(
            db.execute(
                text(
                    """
                    SELECT
                        alert_id,
                        title,
                        event_type,
                        severity_color,
                        country,
                        pub_date_parsed,
                        description,
                        link
                    FROM gdacs_alerts
                    WHERE alert_id = :alert_id
                    """
                ),
                {"alert_id": normalized_event_id},
            )
        )

    mismatch_scores = [row.get("mismatch_score") for row in priority_needs]
    shortage_gaps = [row.get("shortage_gap") for row in priority_needs]

    return {
        "zone": zone,
        "priority_needs": priority_needs,
        "available_surplus": available_surplus,
        "inventory": inventory,
        "requests": requests,
        "related_alert": related_alert,
        "summary_metrics": {
            "total_priority_needs": len(priority_needs),
            "total_surplus_resources": len(available_surplus),
            "highest_mismatch_score": max(mismatch_scores) if mismatch_scores else None,
            "largest_shortage_gap": max(shortage_gaps) if shortage_gaps else None,
            "most_urgent_level": _most_urgent_level(priority_needs),
        },
    }
