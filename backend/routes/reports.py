"""
Summary report endpoints for KPIs and resource analytics.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import get_db, row_to_dict, rows_to_dicts
from rag.llm_briefing import (
    OllamaModelNotFoundError,
    OllamaUnavailableError,
    generate_ai_operational_brief,
)
from rag.rag_briefing import generate_rag_context_for_zone
from rag.simple_retriever import CHUNKS_PATH

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


def _get_zone_by_id(db: Session, zone_id: str) -> dict | None:
    return row_to_dict(
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


def _get_related_alert(db: Session, zone: dict) -> dict | None:
    normalized_event_id = _normalize_crisis_event_id(zone.get("crisis_event_id"))
    if not normalized_event_id:
        return None

    return row_to_dict(
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


def _preview_chunk_text(text_value: str, limit: int = 220) -> str:
    cleaned = " ".join((text_value or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def _format_retrieved_context(retrieved_context: list[dict]) -> list[dict]:
    formatted: list[dict] = []
    for rank, item in enumerate(retrieved_context, start=1):
        final_score = item.get("final_score", item.get("relevance_score"))
        formatted.append(
            {
                "rank": rank,
                "title": item.get("title"),
                "source_type": item.get("source_type"),
                "country": item.get("country"),
                "event_type": item.get("event_type"),
                "url": item.get("url"),
                "relevance_score": final_score,
                "final_score": final_score,
                "semantic_score": item.get("semantic_score"),
                "keyword_score": item.get("keyword_score"),
                "metadata_boost": item.get("metadata_boost"),
                "is_fallback": bool(item.get("is_fallback", False)),
                "preview": _preview_chunk_text(item.get("chunk_text", "")),
            }
        )
    return formatted


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
    zone = _get_zone_by_id(db, zone_id)
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

    related_alert = _get_related_alert(db, zone)

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


@router.get("/rag-zone-context/{zone_id}")
def get_rag_zone_context(zone_id: str, db: Session = Depends(get_db)) -> dict:
    """Return retrieval-based ReliefWeb/GDACS context for one crisis zone."""
    if not Path(CHUNKS_PATH).exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "RAG chunks not found. Run python -m rag.build_corpus and "
                "python -m rag.chunk_documents first."
            ),
        )

    zone = _get_zone_by_id(db, zone_id)
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
                ORDER BY mismatch_score DESC
                LIMIT 5
                """
            ),
            {"zone_id": zone_id},
        )
    )

    related_alert = _get_related_alert(db, zone)

    try:
        rag_result = generate_rag_context_for_zone(
            zone=zone,
            priority_needs=priority_needs,
            related_alert=related_alert,
            top_k=5,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"RAG retrieval failed for zone '{zone_id}': {exc}",
        ) from exc

    return {
        "zone_id": zone.get("zone_id"),
        "zone_name": zone.get("zone_name"),
        "country": zone.get("country"),
        "query": rag_result.get("query", ""),
        "retrieved_context": _format_retrieved_context(rag_result.get("retrieved_context", [])),
        "rag_summary": rag_result.get("rag_summary", ""),
        "transparency_note": (
            "This is retrieval-based context from ReliefWeb/GDACS records. "
            "It is not an LLM-generated analysis."
        ),
    }


@router.get("/ai-zone-briefing/{zone_id}")
def get_ai_zone_briefing(zone_id: str, db: Session = Depends(get_db)) -> dict:
    """Return an AI-assisted operational briefing for one crisis zone."""
    zone = _get_zone_by_id(db, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found")

    briefing_data = get_zone_briefing(zone_id, db)
    priority_needs = briefing_data.get("priority_needs", [])
    inventory = briefing_data.get("inventory", [])
    requests = briefing_data.get("requests", [])
    related_alert = briefing_data.get("related_alert")

    rag_priority_needs = rows_to_dicts(
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
                ORDER BY mismatch_score DESC
                LIMIT 5
                """
            ),
            {"zone_id": zone_id},
        )
    )

    retrieved_context: list[dict] = []
    rag_unavailable = False

    if not Path(CHUNKS_PATH).exists():
        rag_unavailable = True
    else:
        try:
            rag_result = generate_rag_context_for_zone(
                zone=zone,
                priority_needs=rag_priority_needs,
                related_alert=related_alert,
                top_k=5,
            )
            retrieved_context = rag_result.get("retrieved_context", [])
        except Exception:
            rag_unavailable = True
            retrieved_context = []

    try:
        ai_result = generate_ai_operational_brief(
            zone=zone,
            priority_needs=priority_needs,
            inventory=inventory,
            requests_list=requests,
            related_alert=related_alert,
            retrieved_context=retrieved_context,
            rag_unavailable=rag_unavailable,
        )
    except OllamaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OllamaModelNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"AI briefing generation failed for zone '{zone_id}': {exc}",
        ) from exc

    context_used = _format_retrieved_context(retrieved_context[:3])

    return {
        "zone_id": zone.get("zone_id"),
        "zone_name": zone.get("zone_name"),
        "country": zone.get("country"),
        "model": ai_result.get("model"),
        "generation_type": ai_result.get("generation_type"),
        "briefing_text": ai_result.get("briefing_text"),
        "grounding_note": ai_result.get("grounding_note"),
        "transparency_note": ai_result.get("transparency_note"),
        "retrieved_context_used": context_used,
        "rag_context_unavailable": rag_unavailable,
    }
