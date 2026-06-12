"""RAG package: corpus building, chunking, and TF-IDF retrieval."""

__all__ = [
    "build_zone_rag_query",
    "generate_rag_context_for_zone",
    "retrieve_context",
]


def __getattr__(name: str):
    if name == "retrieve_context":
        from rag.simple_retriever import retrieve_context

        return retrieve_context
    if name == "build_zone_rag_query":
        from rag.rag_briefing import build_zone_rag_query

        return build_zone_rag_query
    if name == "generate_rag_context_for_zone":
        from rag.rag_briefing import generate_rag_context_for_zone

        return generate_rag_context_for_zone
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
