"""
Resource coordination endpoints for zones, organizations, inventory, and requests.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import get_db, rows_to_dicts

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("/zones")
def get_zones(db: Session = Depends(get_db)) -> list[dict]:
    """Return all crisis response zones."""
    result = db.execute(
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
            ORDER BY country, zone_name
            """
        )
    )
    return rows_to_dicts(result)


@router.get("/organizations")
def get_organizations(db: Session = Depends(get_db)) -> list[dict]:
    """Return all humanitarian organizations."""
    result = db.execute(
        text(
            """
            SELECT
                org_id,
                org_name,
                org_type,
                country,
                contact_email
            FROM organizations
            ORDER BY org_name
            """
        )
    )
    return rows_to_dicts(result)


@router.get("/inventory")
def get_resource_inventory(
    zone_id: str | None = None,
    resource_type: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    """Return resource inventory with organization and zone details."""
    query = """
        SELECT
            ri.inventory_id,
            ri.org_id,
            o.org_name,
            ri.zone_id,
            z.zone_name,
            z.country,
            ri.resource_type,
            ri.quantity_available,
            ri.unit,
            ri.last_updated
        FROM resource_inventory ri
        JOIN organizations o ON ri.org_id = o.org_id
        JOIN zones z ON ri.zone_id = z.zone_id
        WHERE 1 = 1
    """
    params: dict = {}

    if zone_id:
        query += " AND ri.zone_id = :zone_id"
        params["zone_id"] = zone_id

    if resource_type:
        query += " AND ri.resource_type = :resource_type"
        params["resource_type"] = resource_type

    query += " ORDER BY z.country, z.zone_name, ri.resource_type"

    result = db.execute(text(query), params)
    return rows_to_dicts(result)


@router.get("/requests")
def get_resource_requests(
    zone_id: str | None = None,
    urgency_level: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    """Return resource requests with zone details."""
    query = """
        SELECT
            rr.request_id,
            rr.zone_id,
            z.zone_name,
            z.country,
            rr.resource_type,
            rr.quantity_needed,
            rr.urgency_level,
            rr.requested_by,
            rr.request_timestamp
        FROM resource_requests rr
        JOIN zones z ON rr.zone_id = z.zone_id
        WHERE 1 = 1
    """
    params: dict = {}

    if zone_id:
        query += " AND rr.zone_id = :zone_id"
        params["zone_id"] = zone_id

    if urgency_level:
        query += " AND rr.urgency_level = :urgency_level"
        params["urgency_level"] = urgency_level

    query += " ORDER BY rr.request_timestamp DESC NULLS LAST, z.zone_name"

    result = db.execute(text(query), params)
    return rows_to_dicts(result)
