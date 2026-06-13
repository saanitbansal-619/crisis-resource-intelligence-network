"""
Prepare retrieval-based RAG context for a zone briefing (no LLM yet).
"""

from rag.simple_retriever import retrieve_context

TRANSPARENCY_NOTE = (
    "This is retrieval-based context from ReliefWeb/GDACS records. "
    "It is not an LLM-generated analysis."
)


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


def _format_source_titles(items: list[dict], limit: int) -> str:
    titles: list[str] = []
    seen: set[str] = set()

    for item in items:
        if len(titles) >= limit:
            break

        title = _clean(item.get("title")) or _clean(item.get("source_type")) or "Untitled source"
        source_type = _clean(item.get("source_type")) or "unknown"
        label = f"{title} ({source_type})"

        if label in seen:
            continue
        seen.add(label)
        titles.append(label)

    return "; ".join(titles)


def _build_rag_summary(zone: dict, retrieved_context: list[dict]) -> str:
    country = _clean(zone.get("country")) or "the selected zone"

    if not retrieved_context:
        return (
            "No retrieved context was found from ReliefWeb/GDACS documents for this zone query. "
            f"{TRANSPARENCY_NOTE}"
        )

    country_specific_context = [
        item for item in retrieved_context if not item.get("is_fallback")
    ]
    fallback_context = [item for item in retrieved_context if item.get("is_fallback")]

    parts: list[str] = []

    if country_specific_context:
        parts.append(f"Retrieved country-specific context was found for {country}.")
        country_titles = _format_source_titles(country_specific_context, 3)
        if country_titles:
            parts.append(f"Country-specific sources include: {country_titles}.")
    else:
        parts.append(
            f"No country-specific context was found for {country}. "
            "Fallback results are general humanitarian context and should not be treated as "
            "direct evidence about the selected zone."
        )

    if fallback_context:
        if country_specific_context:
            parts.append(
                "Additional fallback context was included because fewer than the requested number "
                "of country-specific chunks were available. Fallback sources should be treated as "
                f"general humanitarian context, not direct evidence about {country}."
            )

        fallback_titles = _format_source_titles(fallback_context, 2)
        if fallback_titles:
            parts.append(f"Fallback sources include: {fallback_titles}.")

    parts.append(TRANSPARENCY_NOTE)
    return " ".join(parts)


def generate_rag_context_for_zone(
    zone: dict,
    priority_needs: list | None = None,
    related_alert: dict | None = None,
    top_k: int = 5,
) -> dict:
    """Build a zone query, retrieve relevant chunks, and return structured RAG context."""
    query = build_zone_rag_query(zone, priority_needs=priority_needs, related_alert=related_alert)
    retrieved_context = retrieve_context(query, top_k=top_k)
    rag_summary = _build_rag_summary(zone, retrieved_context)

    return {
        "query": query,
        "retrieved_context": retrieved_context,
        "rag_summary": rag_summary,
    }
