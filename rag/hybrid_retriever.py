"""
Hybrid retrieval combining pgvector semantic search, TF-IDF keywords, and metadata boosts.

Run: python -m rag.hybrid_retriever "Chad humanitarian food water displacement needs"
"""

import sys
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import create_engine, text

from rag.semantic_retriever import (
    _preview_text,
    ensure_ollama_ready,
    format_embedding_vector,
    get_database_url,
    get_ollama_embedding,
)
from rag.simple_retriever import (
    CHUNKS_PATH,
    SKIP_REQUESTED_COUNTRIES,
    _country_matches,
    _normalize_text,
    _query_terms,
    load_chunks,
)

SEMANTIC_WEIGHT = 0.60
KEYWORD_WEIGHT = 0.25
COUNTRY_BOOST = 0.35
EVENT_TYPE_BOOST = 0.20
TITLE_BOOST = 0.10
SOURCE_TYPE_BOOST = 0.05

EVENT_TYPE_KEYWORDS = [
    "earthquake",
    "flood",
    "drought",
    "cyclone",
    "storm",
    "wildfire",
    "tsunami",
    "volcano",
    "landslide",
    "hurricane",
    "typhoon",
]


def detect_requested_country(query: str, countries: set[str]) -> str | None:
    query_norm = _normalize_text(query)
    if not query_norm:
        return None

    for country in sorted(countries, key=len, reverse=True):
        country_norm = _normalize_text(country)
        if not country_norm or country_norm in SKIP_REQUESTED_COUNTRIES:
            continue
        if country_norm in query_norm:
            return country
    return None


def detect_requested_event_type(query: str) -> str | None:
    query_norm = _normalize_text(query)
    for event_type in EVENT_TYPE_KEYWORDS:
        if event_type in query_norm:
            return event_type
    return None


def load_countries_from_db(conn) -> set[str]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT country
            FROM rag_chunks
            WHERE country IS NOT NULL AND TRIM(country) <> ''
            """
        )
    ).mappings()
    return {(row["country"] or "").strip() for row in rows if (row["country"] or "").strip()}


def load_scored_db_chunks(conn, query_embedding: list[float]) -> list[dict]:
    rows = conn.execute(
        text(
            """
            SELECT
                chunk_id,
                doc_id,
                source_id,
                source_type,
                title,
                country,
                event_type,
                published_at,
                url,
                chunk_index,
                chunk_text,
                1 - (embedding <=> CAST(:query_embedding AS vector)) AS semantic_score
            FROM rag_chunks
            WHERE embedding IS NOT NULL
            """
        ),
        {"query_embedding": format_embedding_vector(query_embedding)},
    ).mappings()
    return [dict(row) for row in rows]


def build_keyword_scores(query: str, chunks: list[dict]) -> dict[str, float]:
    if not chunks:
        return {}

    chunk_ids = [chunk.get("chunk_id") for chunk in chunks]
    texts = [chunk.get("chunk_text", "") or "" for chunk in chunks]

    try:
        if CHUNKS_PATH.exists():
            json_chunks = load_chunks()
            chunk_ids = [chunk.get("chunk_id") for chunk in json_chunks]
            texts = [chunk.get("chunk_text", "") or "" for chunk in json_chunks]
    except FileNotFoundError:
        pass

    if not any(text.strip() for text in texts):
        return {}

    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform(texts)
    query_vector = vectorizer.transform([query])
    scores = cosine_similarity(query_vector, matrix).flatten()

    keyword_scores: dict[str, float] = {}
    for index, chunk_id in enumerate(chunk_ids):
        if chunk_id:
            keyword_scores[chunk_id] = float(scores[index])
    return keyword_scores


def keyword_overlap_score(query: str, chunk: dict) -> float:
    terms = _query_terms(query)
    if not terms:
        return 0.0

    haystack = _normalize_text(f"{chunk.get('title', '')} {chunk.get('chunk_text', '')}")
    matches = sum(1 for term in terms if term in haystack)
    return matches / len(terms)


def compute_metadata_boost(
    query: str,
    chunk: dict,
    requested_country: str | None,
    requested_event_type: str | None,
) -> float:
    boost = 0.0

    if requested_country and _country_matches(requested_country, chunk.get("country", "")):
        boost += COUNTRY_BOOST

    chunk_event_type = (chunk.get("event_type") or "").strip()
    if requested_event_type and chunk_event_type:
        if _normalize_text(requested_event_type) == _normalize_text(chunk_event_type):
            boost += EVENT_TYPE_BOOST

    title = _normalize_text(chunk.get("title") or "")
    if title:
        terms = _query_terms(query)
        if terms and any(term in title for term in terms):
            boost += TITLE_BOOST

    source_type = (chunk.get("source_type") or "").strip()
    if source_type and _normalize_text(source_type) in _normalize_text(query):
        boost += SOURCE_TYPE_BOOST

    return round(boost, 4)


def _build_result(
    chunk: dict,
    final_score: float,
    semantic_score: float,
    keyword_score: float,
    metadata_boost: float,
    is_fallback: bool,
) -> dict:
    chunk_text = chunk.get("chunk_text") or ""
    return {
        "final_score": round(final_score, 4),
        "semantic_score": round(semantic_score, 4),
        "keyword_score": round(keyword_score, 4),
        "metadata_boost": metadata_boost,
        "is_fallback": is_fallback,
        "chunk_id": chunk.get("chunk_id"),
        "doc_id": chunk.get("doc_id"),
        "source_id": chunk.get("source_id"),
        "title": chunk.get("title"),
        "source_type": chunk.get("source_type"),
        "country": chunk.get("country"),
        "event_type": chunk.get("event_type"),
        "url": chunk.get("url"),
        "chunk_text": chunk_text,
        "preview": _preview_text(chunk_text),
    }


def hybrid_retrieve_context(query: str, top_k: int = 5) -> list[dict]:
    """Combine semantic, keyword, and metadata scores with country-aware fallback."""
    query = (query or "").strip()
    if not query:
        return []

    ensure_ollama_ready()
    query_embedding = get_ollama_embedding(query)
    engine = create_engine(get_database_url())

    with engine.connect() as conn:
        countries = load_countries_from_db(conn)
        db_chunks = load_scored_db_chunks(conn, query_embedding)

    if not db_chunks:
        return []

    requested_country = detect_requested_country(query, countries)
    requested_event_type = detect_requested_event_type(query)
    keyword_scores = build_keyword_scores(query, db_chunks)

    scored_results: list[tuple[float, dict]] = []
    for chunk in db_chunks:
        chunk_id = chunk.get("chunk_id")
        semantic_score = float(chunk.get("semantic_score") or 0)
        keyword_score = keyword_scores.get(chunk_id, keyword_overlap_score(query, chunk))
        metadata_boost = compute_metadata_boost(
            query,
            chunk,
            requested_country,
            requested_event_type,
        )
        final_score = (SEMANTIC_WEIGHT * semantic_score) + (KEYWORD_WEIGHT * keyword_score) + metadata_boost
        scored_results.append(
            (
                final_score,
                _build_result(
                    chunk,
                    final_score,
                    semantic_score,
                    keyword_score,
                    metadata_boost,
                    is_fallback=False,
                ),
            )
        )

    scored_results.sort(key=lambda item: item[0], reverse=True)

    if requested_country:
        country_specific: list[dict] = []
        fallback: list[dict] = []

        for _, result in scored_results:
            is_match = _country_matches(requested_country, result.get("country", ""))
            result["is_fallback"] = not is_match
            if is_match:
                country_specific.append(result)
            else:
                fallback.append(result)

        selected = country_specific[:top_k]
        if len(selected) < top_k:
            selected.extend(fallback[: top_k - len(selected)])
    else:
        selected = [result for _, result in scored_results[:top_k]]
        for result in selected:
            result["is_fallback"] = False

    for rank, result in enumerate(selected, start=1):
        result["rank"] = rank

    return selected


def print_results(
    query: str,
    results: list[dict],
    requested_country: str | None = None,
    requested_event_type: str | None = None,
    top_k: int = 5,
) -> None:
    country_specific_count = sum(1 for result in results if not result.get("is_fallback"))
    fallback_count = sum(1 for result in results if result.get("is_fallback"))

    print(f'Query: "{query}"')
    if requested_country:
        print(f"Requested country: {requested_country}")
    if requested_event_type:
        print(f"Requested event type: {requested_event_type}")
    print(f"Results: {len(results)}")
    print(f"Country-specific results: {country_specific_count}")
    print(f"Fallback results: {fallback_count}")

    if requested_country:
        if country_specific_count == 0:
            print(
                f"Warning: No country-specific context found for {requested_country}. "
                "Showing fallback general humanitarian context."
            )
        elif fallback_count > 0:
            print(
                f"Note: Some fallback results are included because fewer than {top_k} "
                "country-specific chunks were available."
            )

    print("-" * 72)

    if not results:
        print("No hybrid matches found. Run `python -m rag.embed_chunks` first.")
        return

    for result in results:
        is_fallback = bool(result.get("is_fallback"))
        print(f"Rank: {result.get('rank')}")
        print(f"Final score: {result.get('final_score', 0)}")
        print(f"Semantic score: {result.get('semantic_score', 0)}")
        print(f"Keyword score: {result.get('keyword_score', 0)}")
        print(f"Metadata boost: {result.get('metadata_boost', 0)}")
        print(f"Fallback: {'Yes' if is_fallback else 'No'}")
        if is_fallback:
            print(
                "Note: fallback result because not enough country-specific context was available."
            )
        print(f"Title: {result.get('title') or '—'}")
        print(f"Source type: {result.get('source_type') or '—'}")
        print(f"Country: {result.get('country') or '—'}")
        print(f"Event type: {result.get('event_type') or '—'}")
        print(f"URL: {result.get('url') or '—'}")
        print(f"Preview: {result.get('preview', '')}")
        print("-" * 72)


def main() -> None:
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        query = "Chad humanitarian food water displacement needs"

    top_k = 5

    try:
        engine = create_engine(get_database_url())
        with engine.connect() as conn:
            countries = load_countries_from_db(conn)
        requested_country = detect_requested_country(query, countries)
        requested_event_type = detect_requested_event_type(query)
        results = hybrid_retrieve_context(query, top_k=top_k)
    except RuntimeError as exc:
        print(exc)
        sys.exit(1)
    except Exception as exc:
        print(f"Hybrid retrieval failed: {exc}")
        sys.exit(1)

    print_results(
        query,
        results,
        requested_country=requested_country,
        requested_event_type=requested_event_type,
        top_k=top_k,
    )


if __name__ == "__main__":
    main()
