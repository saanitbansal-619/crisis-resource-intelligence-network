"""
Summary report endpoints for KPIs and resource analytics.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from analytics.reallocation_engine import (
    STATUS_PRIORITY,
    build_surplus_records,
    generate_recommendations_from_mismatches,
)
from backend.database import get_db, row_to_dict, rows_to_dicts
from ml_forecasting.feature_builder import (
    FEATURE_NOTE as SHORTAGE_RISK_FEATURE_NOTE,
    FEATURE_QUERY,
    RISK_LEVELS,
    build_raw_records,
)
from ml_forecasting.predict_risk import (
    METHOD_NOTE as SHORTAGE_RISK_METHOD_NOTE,
    METRICS_UNAVAILABLE_MESSAGE as SHORTAGE_RISK_METRICS_UNAVAILABLE_MESSAGE,
    ModelUnavailableError,
    load_model_evaluation,
    predict_shortage_risk,
)
from rag.llm_briefing import (
    OllamaModelNotFoundError,
    OllamaUnavailableError,
    generate_ai_operational_brief,
)
from rag.hybrid_retriever import rag_chunks_available
from rag.rag_briefing import KEYWORD_FALLBACK_NOTE, generate_rag_context_for_zone

URGENCY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}

SHORTAGE_STATUSES = frozenset(
    {"moderate shortage", "severe shortage", "critical shortage"}
)
CRITICAL_SEVERE_STATUSES = frozenset({"critical shortage", "severe shortage"})

SITUATION_REPORT_METHOD_NOTE = (
    "Situation report generated from public crisis records, simulated operational "
    "resource data, mismatch scores, and transfer recommendation logic."
)

SITUATION_REPORT_RECOMMENDED_ACTIONS = [
    "Prioritize response planning for zones with the highest mismatch scores.",
    "Use same-country transfer candidates before considering cross-country fallback options.",
    "Validate fallback transfers with customs, transport, and partner stakeholders before action.",
    "Coordinate dispatch with inventory-holding partners in surplus zones.",
    "Re-run ingestion and mismatch scoring when new crisis or resource data arrives.",
]

SITUATION_REPORT_LIMITATIONS = [
    "Operational inventory and request data are simulated prototype data.",
    "Public crisis context depends on available ReliefWeb/GDACS records.",
    "Transfer recommendations require field validation.",
    "This is a portfolio prototype, not a production emergency response system.",
]

_MISMATCH_WITH_ZONE_QUERY = """
    SELECT
        m.mismatch_id,
        m.zone_id,
        z.zone_name,
        z.country,
        z.admin_region,
        m.resource_type,
        m.total_available,
        m.total_needed,
        m.shortage_gap,
        m.shortage_ratio,
        m.urgency_level,
        m.mismatch_score,
        m.status_label,
        m.calculated_at
    FROM mismatch_scores m
    JOIN zones z ON m.zone_id = z.zone_id
"""


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


def _format_resource_label(resource_type: str | None) -> str:
    if not resource_type:
        return "resource"
    return str(resource_type).replace("_", " ").title()


def _fetch_mismatch_rows(db: Session) -> list[dict]:
    result = db.execute(text(_MISMATCH_WITH_ZONE_QUERY + " ORDER BY m.mismatch_score DESC"))
    return rows_to_dicts(result)


def _fetch_overview_counts(db: Session) -> dict:
    result = db.execute(
        text(
            """
            SELECT
                (SELECT COUNT(*) FROM zones) AS total_zones,
                (SELECT COUNT(*) FROM mismatch_scores WHERE status_label = 'critical shortage')
                    AS critical_shortage_count,
                (SELECT COUNT(*) FROM mismatch_scores WHERE status_label = 'severe shortage')
                    AS severe_shortage_count,
                (SELECT COUNT(*) FROM mismatch_scores WHERE status_label = 'surplus')
                    AS surplus_count
            """
        )
    )
    return row_to_dict(result) or {}


def _build_top_priority_zones(mismatch_rows: list[dict], limit: int = 5) -> list[dict]:
    zone_map: dict[str, dict] = {}

    for row in mismatch_rows:
        status = (row.get("status_label") or "").strip().lower()
        if status not in SHORTAGE_STATUSES:
            continue

        zone_id = row.get("zone_id")
        if not zone_id:
            continue

        entry = zone_map.setdefault(
            zone_id,
            {
                "zone_id": zone_id,
                "zone_name": row.get("zone_name") or zone_id,
                "country": row.get("country") or "—",
                "highest_priority_score": 0.0,
                "largest_shortage_gap": 0,
                "most_urgent_level": None,
                "_urgent_rank": 0,
                "_resource_candidates": [],
            },
        )

        score = float(row.get("mismatch_score") or 0)
        gap = int(row.get("shortage_gap") or 0)
        entry["highest_priority_score"] = max(entry["highest_priority_score"], score)
        entry["largest_shortage_gap"] = max(entry["largest_shortage_gap"], gap)

        urgency = row.get("urgency_level")
        urgent_rank = URGENCY_RANK.get(urgency, 0)
        if urgent_rank > entry["_urgent_rank"]:
            entry["_urgent_rank"] = urgent_rank
            entry["most_urgent_level"] = urgency

        resource_type = row.get("resource_type")
        if resource_type and gap > 0:
            entry["_resource_candidates"].append((score, gap, resource_type))

    ranked: list[dict] = []
    for entry in zone_map.values():
        seen: set[str] = set()
        key_resources: list[str] = []
        for _, _, resource_type in sorted(
            entry["_resource_candidates"],
            key=lambda item: (-item[0], -item[1]),
        ):
            if resource_type in seen:
                continue
            seen.add(resource_type)
            key_resources.append(resource_type)
            if len(key_resources) >= 3:
                break

        ranked.append(
            {
                "zone_id": entry["zone_id"],
                "zone_name": entry["zone_name"],
                "country": entry["country"],
                "highest_priority_score": entry["highest_priority_score"],
                "largest_shortage_gap": entry["largest_shortage_gap"],
                "most_urgent_level": entry["most_urgent_level"],
                "key_shortage_resources": key_resources,
                "_urgent_rank": entry["_urgent_rank"],
            }
        )

    ranked.sort(
        key=lambda item: (
            -item["highest_priority_score"],
            -item["largest_shortage_gap"],
            -item["_urgent_rank"],
        )
    )

    for item in ranked:
        item.pop("_urgent_rank", None)

    return ranked[:limit]


def _build_critical_shortages(mismatch_rows: list[dict], limit: int = 10) -> list[dict]:
    shortages: list[dict] = []
    for row in mismatch_rows:
        status = (row.get("status_label") or "").strip().lower()
        if status not in CRITICAL_SEVERE_STATUSES:
            continue

        shortages.append(
            {
                "zone_name": row.get("zone_name") or row.get("zone_id") or "Unknown Zone",
                "country": row.get("country") or "—",
                "resource_type": row.get("resource_type"),
                "total_available": int(row.get("total_available") or 0),
                "total_needed": int(row.get("total_needed") or 0),
                "shortage_gap": int(row.get("shortage_gap") or 0),
                "urgency_level": row.get("urgency_level") or "—",
                "mismatch_score": float(row.get("mismatch_score") or 0),
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
    return shortages[:limit]


def _build_available_surplus(mismatch_rows: list[dict], limit: int = 10) -> list[dict]:
    surplus_records = build_surplus_records(mismatch_rows)
    surplus_records.sort(key=lambda item: -int(item.get("surplus_amount") or 0))
    return [
        {
            "zone_name": item.get("zone_name"),
            "country": item.get("country"),
            "resource_type": item.get("resource_type"),
            "surplus_amount": item.get("surplus_amount"),
            "available_amount": item.get("available_amount"),
            "status": item.get("status"),
        }
        for item in surplus_records[:limit]
    ]


def _shape_transfer_recommendations(recommendations: list[dict], limit: int = 5) -> list[dict]:
    shaped: list[dict] = []
    for item in recommendations[:limit]:
        shaped.append(
            {
                "resource_type": item.get("resource_type"),
                "from_zone_name": item.get("from_zone_name"),
                "to_zone_name": item.get("to_zone_name"),
                "recommended_quantity": item.get("recommended_quantity"),
                "confidence_level": item.get("confidence_level"),
                "match_type": item.get("match_type"),
                "feasibility_note": item.get("feasibility_note"),
            }
        )
    return shaped


def _build_operational_interpretation(
    top_priority_zones: list[dict],
    critical_shortages: list[dict],
    recommended_transfers: list[dict],
) -> str:
    zone_names = [
        zone.get("zone_name")
        for zone in top_priority_zones[:2]
        if zone.get("zone_name")
    ]
    if len(zone_names) >= 2:
        zones_phrase = f"{zone_names[0]} and {zone_names[1]}"
    elif len(zone_names) == 1:
        zones_phrase = zone_names[0]
    else:
        zones_phrase = "multiple monitored zones"

    resource_scores: dict[str, float] = {}
    for row in critical_shortages:
        resource_type = row.get("resource_type")
        if not resource_type:
            continue
        score = float(row.get("mismatch_score") or 0)
        resource_scores[resource_type] = max(resource_scores.get(resource_type, 0.0), score)

    top_resources = sorted(resource_scores.items(), key=lambda item: -item[1])[:2]
    if len(top_resources) >= 2:
        resources_phrase = (
            f"{_format_resource_label(top_resources[0][0])} and "
            f"{_format_resource_label(top_resources[1][0])}"
        )
    elif len(top_resources) == 1:
        resources_phrase = _format_resource_label(top_resources[0][0])
    else:
        resources_phrase = "critical humanitarian supplies"

    has_fallback = any(
        item.get("match_type") == "cross_country_fallback" for item in recommended_transfers
    )
    if has_fallback:
        transfer_phrase = (
            "Same-country transfer recommendations should be prioritized before "
            "cross-country fallback candidates."
        )
    else:
        transfer_phrase = (
            "Same-country transfer recommendations should be prioritized where available."
        )

    return (
        f"The current operational picture shows concentrated critical shortages in {zones_phrase}. "
        f"{resources_phrase} are the highest-priority resource gaps. "
        f"{transfer_phrase}"
    )


def _preview_chunk_text(text_value: str, limit: int = 220) -> str:
    cleaned = " ".join((text_value or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def _count_rag_chunks(db: Session) -> int:
    try:
        row = row_to_dict(db.execute(text("SELECT COUNT(*) AS count FROM rag_chunks")))
        return int((row or {}).get("count") or 0)
    except Exception:
        return 0


def _rag_data_available(db: Session) -> bool:
    if _count_rag_chunks(db) > 0:
        return True
    return rag_chunks_available()


def _rag_transparency_note(retrieval_mode: str) -> str:
    base_note = (
        "This is retrieval-based context from ReliefWeb/GDACS records. "
        "It is not an LLM-generated analysis."
    )
    if retrieval_mode == "keyword_fallback":
        return f"{KEYWORD_FALLBACK_NOTE} {base_note}"
    return base_note


def _format_retrieved_context(retrieved_context: list[dict]) -> list[dict]:
    """Shape hybrid retrieval results for API and dashboard consumers."""
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
                "retrieval_mode": item.get("retrieval_mode"),
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


@router.get("/situation-report")
def get_situation_report(db: Session = Depends(get_db)) -> dict:
    """Return a deterministic overall operational situation report across all zones."""
    overview_counts = _fetch_overview_counts(db)
    mismatch_rows = _fetch_mismatch_rows(db)
    reallocation_payload = generate_recommendations_from_mismatches(mismatch_rows)
    recommendations = reallocation_payload.get("recommendations") or []

    top_priority_zones = _build_top_priority_zones(mismatch_rows, limit=5)
    critical_shortages = _build_critical_shortages(mismatch_rows, limit=10)
    recommended_transfers = _shape_transfer_recommendations(recommendations, limit=5)
    available_surplus = _build_available_surplus(mismatch_rows, limit=10)

    return {
        "report_title": "Overall Situation Report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_zones": int(overview_counts.get("total_zones") or 0),
            "critical_shortage_count": int(overview_counts.get("critical_shortage_count") or 0),
            "severe_shortage_count": int(overview_counts.get("severe_shortage_count") or 0),
            "surplus_count": int(overview_counts.get("surplus_count") or 0),
            "recommended_transfer_count": len(recommendations),
        },
        "top_priority_zones": top_priority_zones,
        "critical_shortages": critical_shortages,
        "recommended_transfers": recommended_transfers,
        "available_surplus": available_surplus,
        "operational_interpretation": _build_operational_interpretation(
            top_priority_zones,
            critical_shortages,
            recommended_transfers,
        ),
        "recommended_actions": list(SITUATION_REPORT_RECOMMENDED_ACTIONS),
        "limitations": list(SITUATION_REPORT_LIMITATIONS),
        "method_note": SITUATION_REPORT_METHOD_NOTE,
    }


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
    if not _rag_data_available(db):
        raise HTTPException(
            status_code=503,
            detail=(
                "No RAG chunks were found in the database. Load embedded ReliefWeb/GDACS "
                "chunks into rag_chunks before requesting retrieved context."
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

    retrieval_mode = rag_result.get("retrieval_mode") or "hybrid"
    retrieved_context = rag_result.get("retrieved_context") or []
    if not retrieved_context:
        raise HTTPException(
            status_code=503,
            detail=(
                "No matching RAG chunks were found for this zone query. "
                "Confirm rag_chunks contains embedded ReliefWeb/GDACS data."
            ),
        )

    return {
        "zone_id": zone.get("zone_id"),
        "zone_name": zone.get("zone_name"),
        "country": zone.get("country"),
        "query": rag_result.get("query", ""),
        "retrieval_mode": retrieval_mode,
        "retrieved_context": _format_retrieved_context(retrieved_context),
        "rag_summary": rag_result.get("rag_summary", ""),
        "transparency_note": _rag_transparency_note(retrieval_mode),
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

    if _rag_data_available(db):
        try:
            rag_result = generate_rag_context_for_zone(
                zone=zone,
                priority_needs=rag_priority_needs,
                related_alert=related_alert,
                top_k=5,
            )
            retrieved_context = rag_result.get("retrieved_context", [])
            if not retrieved_context:
                rag_unavailable = True
        except Exception:
            rag_unavailable = True
            retrieved_context = []
    else:
        rag_unavailable = True

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


SHORTAGE_RISK_UNAVAILABLE_NOTE = (
    "Shortage-risk forecasting is a prototype layer using simulated/proxy labels. "
    "It is currently unavailable; the OR-Tools optimization plan and deterministic "
    "analytics remain available."
)


def _load_forecast_records(db: Session) -> list[dict]:
    """Load raw feature records for forecasting using the shared FEATURE_QUERY."""
    rows = rows_to_dicts(db.execute(text(FEATURE_QUERY)))
    return build_raw_records(rows)


def _summarize_forecasts(forecasts: list[dict]) -> dict:
    by_level = {level: 0 for level in RISK_LEVELS}
    for item in forecasts:
        level = item.get("predicted_48h_risk")
        if level in by_level:
            by_level[level] += 1
    high_or_critical = by_level.get("high", 0) + by_level.get("critical", 0)
    return {
        "total_forecasts": len(forecasts),
        "by_predicted_48h_risk": by_level,
        "high_or_critical_count": high_or_critical,
    }


@router.get("/shortage-risk-forecast")
def get_shortage_risk_forecast(db: Session = Depends(get_db)) -> dict:
    """Return prototype 48-72 hour shortage-risk forecasts for crisis zones.

    Gracefully reports unavailability when the trained model or feature data is
    missing, instead of raising a server error.
    """
    evaluation = load_model_evaluation()
    model_evaluation = (
        evaluation
        if evaluation is not None
        else {"message": SHORTAGE_RISK_METRICS_UNAVAILABLE_MESSAGE}
    )

    base_response = {
        "status": "unavailable",
        "model_available": False,
        "model_note": SHORTAGE_RISK_METHOD_NOTE,
        "feature_note": SHORTAGE_RISK_FEATURE_NOTE,
        "model_evaluation": model_evaluation,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": _summarize_forecasts([]),
        "forecasts": [],
    }

    try:
        records = _load_forecast_records(db)
    except Exception:
        base_response["message"] = (
            "Forecast feature data is unavailable (database tables or sample data missing). "
            + SHORTAGE_RISK_UNAVAILABLE_NOTE
        )
        return base_response

    if not records:
        base_response["status"] = "no_data"
        base_response["message"] = (
            "No mismatch records are available to forecast. " + SHORTAGE_RISK_UNAVAILABLE_NOTE
        )
        return base_response

    try:
        predictions = predict_shortage_risk(records)
    except ModelUnavailableError as exc:
        base_response["message"] = (
            f"{exc} To enable forecasts, train the model with: "
            "python -m ml_forecasting.train_model"
        )
        return base_response
    except Exception as exc:  # pragma: no cover - defensive
        base_response["message"] = (
            f"Shortage-risk forecasting failed: {exc}. " + SHORTAGE_RISK_UNAVAILABLE_NOTE
        )
        return base_response

    forecasts = [
        {
            "zone_name": item.get("zone_name"),
            "country": item.get("country"),
            "resource_type": item.get("resource_type"),
            "current_shortage_gap": item.get("current_shortage_gap"),
            "fulfillment_ratio": item.get("fulfillment_ratio"),
            "predicted_48h_risk": item.get("predicted_48h_risk"),
            "predicted_72h_risk": item.get("predicted_72h_risk"),
            "confidence": item.get("confidence"),
            "model_note": item.get("model_note"),
        }
        for item in predictions
    ]

    risk_order = {level: index for index, level in enumerate(RISK_LEVELS)}
    forecasts.sort(
        key=lambda item: (
            risk_order.get(item.get("predicted_48h_risk"), 0),
            item.get("current_shortage_gap") or 0,
        ),
        reverse=True,
    )

    return {
        "status": "ok",
        "model_available": True,
        "model_note": SHORTAGE_RISK_METHOD_NOTE,
        "feature_note": SHORTAGE_RISK_FEATURE_NOTE,
        "model_evaluation": model_evaluation,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": _summarize_forecasts(forecasts),
        "forecasts": forecasts,
    }
