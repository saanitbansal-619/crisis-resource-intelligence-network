"""
Supply-demand mismatch analytics endpoints.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import get_db, rows_to_dicts
from analytics.reallocation_engine import generate_recommendations_from_mismatches

router = APIRouter(prefix="/mismatches", tags=["mismatches"])


def _mismatch_base_query() -> str:
    """Shared SELECT for mismatch endpoints with zone context."""
    return """
        SELECT
            m.mismatch_id,
            m.zone_id,
            z.zone_name,
            z.country,
            z.admin_region,
            z.latitude,
            z.longitude,
            m.resource_type,
            m.total_available,
            m.total_needed,
            m.shortage_gap,
            m.shortage_ratio,
            m.urgency_level,
            m.urgency_weight,
            m.mismatch_score,
            m.status_label,
            m.calculated_at
        FROM mismatch_scores m
        JOIN zones z ON m.zone_id = z.zone_id
        WHERE 1 = 1
    """


@router.get("")
def get_mismatches(
    status_label: str | None = None,
    zone_id: str | None = None,
    resource_type: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Return mismatch scores with optional filters."""
    query = _mismatch_base_query()
    params: dict = {"limit": limit}

    if status_label:
        query += " AND m.status_label = :status_label"
        params["status_label"] = status_label

    if zone_id:
        query += " AND m.zone_id = :zone_id"
        params["zone_id"] = zone_id

    if resource_type:
        query += " AND m.resource_type = :resource_type"
        params["resource_type"] = resource_type

    query += " ORDER BY m.mismatch_score DESC LIMIT :limit"

    result = db.execute(text(query), params)
    return rows_to_dicts(result)


@router.get("/critical")
def get_critical_mismatches(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Return critical shortages ordered by mismatch score."""
    result = db.execute(
        text(
            _mismatch_base_query()
            + """
            AND m.status_label = 'critical shortage'
            ORDER BY m.mismatch_score DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    )
    return rows_to_dicts(result)


@router.get("/severe")
def get_severe_mismatches(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Return critical and severe shortages ordered by mismatch score."""
    result = db.execute(
        text(
            _mismatch_base_query()
            + """
            AND m.status_label IN ('critical shortage', 'severe shortage')
            ORDER BY m.mismatch_score DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    )
    return rows_to_dicts(result)


@router.get("/surplus")
def get_surplus_mismatches(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Return surplus resources ordered by shortage gap ascending."""
    result = db.execute(
        text(
            _mismatch_base_query()
            + """
            AND m.status_label = 'surplus'
            ORDER BY m.shortage_gap ASC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    )
    return rows_to_dicts(result)


@router.get("/reallocation-recommendations")
def get_reallocation_recommendations(db: Session = Depends(get_db)) -> dict:
    """Return deterministic surplus-to-shortage transfer recommendations."""
    result = db.execute(
        text(
            _mismatch_base_query()
            + """
            ORDER BY m.mismatch_score DESC
            """
        )
    )
    return generate_recommendations_from_mismatches(rows_to_dicts(result))
