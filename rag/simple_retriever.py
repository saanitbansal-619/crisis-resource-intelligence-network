"""
TF-IDF retrieval over local RAG chunks with lightweight metadata boosting.

Run: python -m rag.simple_retriever "Philippines earthquake water food medical needs"
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHUNKS_PATH = PROJECT_ROOT / "data" / "rag" / "chunks.json"

MIN_RELEVANCE_SCORE = 0.01
COUNTRY_BOOST = 0.35
EVENT_TYPE_BOOST = 0.20
TITLE_BOOST = 0.10
SOURCE_TYPE_BOOST = 0.05

SKIP_REQUESTED_COUNTRIES = {"world"}
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "were",
    "with",
}


def load_chunks(path: Path = CHUNKS_PATH) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"Chunks file not found: {path}. Run `python -m rag.chunk_documents` first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", (value or "").strip().casefold())
    return text


def build_country_set(chunks: list[dict]) -> set[str]:
    countries: set[str] = set()
    for chunk in chunks:
        country = (chunk.get("country") or "").strip()
        if country:
            countries.add(country)
    return countries


def detect_requested_country(query: str, chunks: list[dict]) -> str | None:
    query_norm = _normalize_text(query)
    if not query_norm:
        return None

    for country in sorted(build_country_set(chunks), key=len, reverse=True):
        country_norm = _normalize_text(country)
        if not country_norm or country_norm in SKIP_REQUESTED_COUNTRIES:
            continue
        if country_norm in query_norm:
            return country
    return None


def _query_terms(query: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", _normalize_text(query))
    return [token for token in tokens if len(token) >= 3 and token not in STOP_WORDS]


def _country_matches(requested_country: str | None, chunk_country: str) -> bool:
    if not requested_country or not chunk_country:
        return False

    requested_norm = _normalize_text(requested_country)
    chunk_norm = _normalize_text(chunk_country)
    if not requested_norm or not chunk_norm:
        return False

    return requested_norm == chunk_norm or requested_norm in chunk_norm


def compute_metadata_boost(query: str, chunk: dict) -> float:
    query_norm = _normalize_text(query)
    boost = 0.0

    country = (chunk.get("country") or "").strip()
    if country and _normalize_text(country) in query_norm:
        boost += COUNTRY_BOOST

    event_type = (chunk.get("event_type") or "").strip()
    if event_type and _normalize_text(event_type) in query_norm:
        boost += EVENT_TYPE_BOOST

    title = _normalize_text(chunk.get("title") or "")
    if title:
        terms = _query_terms(query)
        if terms and any(term in title for term in terms):
            boost += TITLE_BOOST

    source_type = (chunk.get("source_type") or "").strip()
    if source_type and _normalize_text(source_type) in query_norm:
        boost += SOURCE_TYPE_BOOST

    return round(boost, 4)


def _build_result(
    chunk: dict,
    final_score: float,
    tfidf_score: float,
    metadata_boost: float,
    is_fallback: bool,
) -> dict:
    result = dict(chunk)
    result["relevance_score"] = final_score
    result["tfidf_score"] = round(tfidf_score, 4)
    result["metadata_boost"] = metadata_boost
    result["is_fallback"] = is_fallback
    return result


def retrieve_context(query: str, top_k: int = 5, min_score: float = MIN_RELEVANCE_SCORE) -> list[dict]:
    chunks = load_chunks()
    if not chunks:
        return []

    query = (query or "").strip()
    if not query:
        return []

    requested_country = detect_requested_country(query, chunks)

    texts = [chunk.get("chunk_text", "") for chunk in chunks]
    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform(texts)
    query_vector = vectorizer.transform([query])
    tfidf_scores = cosine_similarity(query_vector, matrix).flatten()

    scored_results: list[tuple[float, float, float, dict]] = []
    for index, chunk in enumerate(chunks):
        tfidf_score = float(tfidf_scores[index])
        metadata_boost = compute_metadata_boost(query, chunk)
        final_score = round(tfidf_score + metadata_boost, 4)

        if tfidf_score < min_score and metadata_boost == 0:
            continue

        scored_results.append((final_score, tfidf_score, metadata_boost, chunk))

    scored_results.sort(key=lambda item: item[0], reverse=True)

    if requested_country:
        country_specific_results: list[dict] = []
        fallback_results: list[dict] = []

        for final_score, tfidf_score, metadata_boost, chunk in scored_results:
            is_country_match = _country_matches(requested_country, chunk.get("country", ""))
            result = _build_result(
                chunk,
                final_score,
                tfidf_score,
                metadata_boost,
                is_fallback=not is_country_match,
            )
            if is_country_match:
                country_specific_results.append(result)
            else:
                fallback_results.append(result)

        results = country_specific_results[:top_k]
        if len(results) < top_k:
            remaining = top_k - len(results)
            results.extend(fallback_results[:remaining])
        return results

    return [
        _build_result(chunk, final_score, tfidf_score, metadata_boost, is_fallback=False)
        for final_score, tfidf_score, metadata_boost, chunk in scored_results[:top_k]
    ]


def _preview_text(text: str, limit: int = 220) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def print_results(
    query: str,
    results: list[dict],
    chunks: list[dict] | None = None,
    top_k: int = 5,
) -> None:
    if chunks is None:
        chunks = load_chunks()

    requested_country = detect_requested_country(query, chunks)
    country_specific_count = sum(1 for result in results if not result.get("is_fallback"))
    fallback_count = sum(1 for result in results if result.get("is_fallback"))

    print(f'Query: "{query}"')
    if requested_country:
        print(f"Requested country: {requested_country}")
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
        print("No relevant chunks found.")
        return

    for rank, result in enumerate(results, start=1):
        is_fallback = bool(result.get("is_fallback"))
        print(f"Rank: {rank}")
        print(f"Final relevance score: {result.get('relevance_score', 0)}")
        print(f"TF-IDF score: {result.get('tfidf_score', 0)}")
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
        print(f"Preview: {_preview_text(result.get('chunk_text', ''))}")
        print("-" * 72)


def main() -> None:
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        query = "Philippines earthquake water food medical needs"

    top_k = 5
    chunks = load_chunks()
    results = retrieve_context(query, top_k=top_k)
    print_results(query, results, chunks, top_k=top_k)


if __name__ == "__main__":
    main()
