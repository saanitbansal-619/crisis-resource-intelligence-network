"""
Prepare retrieval-based RAG context for a zone briefing (no LLM yet).
"""

from rag.simple_retriever import retrieve_context


def _clean(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _format_resource_name(resource_type: str) -> str:
    if not resource_type:
        return ""
    return resource_type.replace("_", " ").title()


def build_zone_rag_query(
    zone: dict,
    priority_needs: list | None = None,
    related_alert: dict | None = None,
) -> str:
    """Build a retrieval query from zone metadata, alert context, and priority needs."""
    parts: list[str] = []

    zone_name = _clean(zone.get("zone_name"))
    country = _clean(zone.get("country"))
    admin_region = _clean(zone.get("admin_region"))

    if zone_name:
        parts.append(zone_name)
    if country:
        parts.append(country)
    if admin_region:
        parts.append(admin_region)

    if related_alert:
        alert_title = _clean(related_alert.get("title"))
        alert_event_type = _clean(related_alert.get("event_type"))
        if alert_title:
            parts.append(alert_title)
        if alert_event_type:
            parts.append(alert_event_type)

    if priority_needs:
        for need in priority_needs[:3]:
            resource_type = _format_resource_name(_clean(need.get("resource_type")))
            if resource_type:
                parts.append(resource_type)
            status_label = _clean(need.get("status_label"))
            if status_label:
                parts.append(status_label.replace("_", " "))

    return " ".join(part for part in parts if part)


def _build_rag_summary(query: str, retrieved_context: list[dict]) -> str:
    if not retrieved_context:
        return (
            "No retrieved context was found from ReliefWeb/GDACS documents for this zone query. "
            "This is retrieval-based context only and not an LLM-generated analysis."
        )

    country_hint = next((item.get("country") for item in retrieved_context if item.get("country")), "")
    event_hint = next((item.get("event_type") for item in retrieved_context if item.get("event_type")), "")

    location_parts = [part for part in [country_hint, event_hint] if part]
    location_text = " / ".join(location_parts) if location_parts else "the selected crisis context"

    top_sources = []
    for item in retrieved_context[:3]:
        title = _clean(item.get("title")) or _clean(item.get("source_type")) or "Untitled source"
        source_type = _clean(item.get("source_type")) or "unknown"
        top_sources.append(f"{title} ({source_type})")

    sources_text = "; ".join(top_sources)

    return (
        f"Retrieved context was found from ReliefWeb/GDACS documents related to {location_text}. "
        f"The top sources include: {sources_text}. "
        "This is retrieval-based context only and not an LLM-generated analysis."
    )


def generate_rag_context_for_zone(
    zone: dict,
    priority_needs: list | None = None,
    related_alert: dict | None = None,
    top_k: int = 5,
) -> dict:
    """Build a zone query, retrieve relevant chunks, and return structured RAG context."""
    query = build_zone_rag_query(zone, priority_needs=priority_needs, related_alert=related_alert)
    retrieved_context = retrieve_context(query, top_k=top_k)
    rag_summary = _build_rag_summary(query, retrieved_context)

    return {
        "query": query,
        "retrieved_context": retrieved_context,
        "rag_summary": rag_summary,
    }
