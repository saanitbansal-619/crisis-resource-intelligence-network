"""
Crisis endpoints for ReliefWeb reports and GDACS alerts.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import get_db, row_to_dict, rows_to_dicts

router = APIRouter(prefix="/crises", tags=["crises"])


@router.get("/reports")
def get_crisis_reports(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Return latest ReliefWeb crisis reports."""
    result = db.execute(
        text(
            """
            SELECT
                reliefweb_id,
                title,
                countries,
                primary_country,
                date_parsed,
                source_name,
                disaster_types,
                themes,
                url
            FROM crisis_reports
            ORDER BY date_parsed DESC NULLS LAST
            LIMIT :limit
            """
        ),
        {"limit": limit},
    )
    return rows_to_dicts(result)


@router.get("/alerts")
def get_gdacs_alerts(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Return latest GDACS disaster alerts."""
    result = db.execute(
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
            ORDER BY pub_date_parsed DESC NULLS LAST
            LIMIT :limit
            """
        ),
        {"limit": limit},
    )
    return rows_to_dicts(result)


@router.get("/alerts/{alert_id}")
def get_gdacs_alert(alert_id: str, db: Session = Depends(get_db)) -> dict:
    """Return a single GDACS alert by ID."""
    result = db.execute(
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
        {"alert_id": alert_id},
    )
    alert = row_to_dict(result)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"GDACS alert '{alert_id}' not found.")
    return alert
