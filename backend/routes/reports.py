"""
Summary report endpoints for KPIs and resource analytics.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import get_db, row_to_dict, rows_to_dicts

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
