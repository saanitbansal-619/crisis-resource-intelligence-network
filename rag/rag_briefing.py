"""
Prepare retrieval-based RAG context for zone briefings and AI-assisted drafts.
"""

from rag.hybrid_retriever import retrieve_context_with_mode

TRANSPARENCY_NOTE = (
    "This is retrieval-based context from ReliefWeb/GDACS records. "
    "It is not an LLM-generated analysis."
)
KEYWORD_FALLBACK_NOTE = (
    "Semantic retrieval is unavailable in hosted mode, showing keyword-based retrieved crisis context."
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


def _normalize_retrieved_context(retrieved_context: list[dict]) -> list[dict]:
    """Normalize hybrid retrieval fields for API and dashboard consumers."""
    normalized: list[dict] = []
    for item in retrieved_context:
        result = dict(item)
        final_score = result.get("final_score")
        relevance_score = result.get("relevance_score")

        if final_score is not None:
            result["relevance_score"] = final_score
        elif relevance_score is not None:
            result["final_score"] = relevance_score

        result.pop("tfidf_score", None)
        normalized.append(result)
    return normalized


def _build_rag_summary(
    zone: dict,
    retrieved_context: list[dict],
    top_k: int = 5,
    retrieval_mode: str = "hybrid",
) -> str:
    country = _clean(zone.get("country")) or "the selected zone"

    if not retrieved_context:
        if retrieval_mode == "keyword_fallback":
            return (
                f"{KEYWORD_FALLBACK_NOTE} No matching ReliefWeb/GDACS chunks were found for this zone query. "
                f"{TRANSPARENCY_NOTE}"
            )
        return (
            "No retrieved context was found from ReliefWeb/GDACS documents for this zone query. "
            f"{TRANSPARENCY_NOTE}"
        )

    country_specific_context = [
        item for item in retrieved_context if not item.get("is_fallback")
    ]
    fallback_context = [item for item in retrieved_context if item.get("is_fallback")]

    parts: list[str] = []

    if retrieval_mode == "keyword_fallback":
        parts.append(KEYWORD_FALLBACK_NOTE)

    if country_specific_context:
        count = len(country_specific_context)
        source_label = "source" if count == 1 else "sources"
        if retrieval_mode == "keyword_fallback":
            parts.append(
                f"Keyword-based country-specific context found for {country} ({count} {source_label})."
            )
        else:
            parts.append(f"Country-specific context found for {country} ({count} {source_label}).")
            parts.append(
                "Context was retrieved using hybrid semantic and keyword search over ReliefWeb/GDACS records."
            )
    else:
        parts.append(
            f"No country-specific context was found for {country}. "
            "Fallback results are general humanitarian context and should not be treated as "
            "direct evidence about the selected zone."
        )

    if fallback_context and country_specific_context:
        parts.append(
            f"Additional fallback context is included because fewer than {top_k} "
            f"country-specific chunks were available. Fallback sources should be treated as "
            f"general humanitarian context, not direct evidence about {country}."
        )

    parts.append(TRANSPARENCY_NOTE)
    return " ".join(parts)


def build_keyword_fallback_context(
    zone: dict,
    retrieved_context: list[dict] | None = None,
    top_k: int = 5,
) -> dict:
    """Build keyword-fallback context from already-retrieved chunks.

    This helper does not require Ollama or live retrieval. It mirrors the
    hosted-mode (keyword fallback) shape used by ``generate_rag_context_for_zone``
    so the fallback behavior can be exercised with sample data.
    """
    normalized = _normalize_retrieved_context(retrieved_context or [])
    rag_summary = _build_rag_summary(
        zone,
        normalized,
        top_k=top_k,
        retrieval_mode="keyword_fallback",
    )
    return {
        "retrieved_context": normalized,
        "rag_summary": rag_summary,
        "retrieval_mode": "keyword_fallback",
        "is_fallback": True,
    }


def generate_rag_context_for_zone(
    zone: dict,
    priority_needs: list | None = None,
    related_alert: dict | None = None,
    top_k: int = 5,
) -> dict:
    """Build a zone query, retrieve relevant chunks, and return structured RAG context."""
    query = build_zone_rag_query(zone, priority_needs=priority_needs, related_alert=related_alert)
    retrieved_context, retrieval_mode = retrieve_context_with_mode(query, top_k=top_k)
    retrieved_context = _normalize_retrieved_context(retrieved_context)
    rag_summary = _build_rag_summary(
        zone,
        retrieved_context,
        top_k=top_k,
        retrieval_mode=retrieval_mode,
    )

    return {
        "query": query,
        "retrieved_context": retrieved_context,
        "rag_summary": rag_summary,
        "retrieval_mode": retrieval_mode,
    }
