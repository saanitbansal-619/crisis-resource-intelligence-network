"""
Semantic retrieval over pgvector-backed RAG chunks using Ollama embeddings.

Run: python -m rag.semantic_retriever "Philippines earthquake water food medical needs"
"""

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

OLLAMA_EMBEDDINGS_URL = "http://localhost:11434/api/embeddings"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
EMBEDDING_MODEL = "nomic-embed-text"

OLLAMA_UNAVAILABLE_MESSAGE = (
    "Ollama is not running. Start Ollama and make sure `ollama list` shows nomic-embed-text."
)

load_dotenv(dotenv_path=ENV_PATH, override=True, encoding="utf-8-sig")


def parse_database_url_manual(env_path: Path) -> str | None:
    if not env_path.exists():
        return None

    with env_path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped.startswith("DATABASE_URL="):
                return stripped.split("=", 1)[1].strip()

    return None


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL") or parse_database_url_manual(ENV_PATH)
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL not found. Create a .env file in the project root using .env.example."
        )
    return database_url


def format_embedding_vector(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def ensure_ollama_ready() -> None:
    try:
        response = requests.get(OLLAMA_TAGS_URL, timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"{OLLAMA_UNAVAILABLE_MESSAGE} Details: {exc}") from exc


def get_ollama_embedding(prompt: str) -> list[float]:
    response = requests.post(
        OLLAMA_EMBEDDINGS_URL,
        json={"model": EMBEDDING_MODEL, "prompt": prompt},
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    embedding = payload.get("embedding")
    if not embedding:
        raise RuntimeError("Ollama embeddings response did not include an embedding vector.")
    return embedding


def _preview_text(text: str, limit: int = 220) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def semantic_retrieve_context(query: str, top_k: int = 5) -> list[dict]:
    """Embed the query and return top-k semantically similar RAG chunks."""
    query = (query or "").strip()
    if not query:
        return []

    ensure_ollama_ready()
    query_embedding = get_ollama_embedding(query)
    engine = create_engine(get_database_url())

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT
                    chunk_id,
                    source_id,
                    source_type,
                    title,
                    country,
                    event_type,
                    url,
                    chunk_text,
                    1 - (embedding <=> CAST(:query_embedding AS vector)) AS semantic_score
                FROM rag_chunks
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:query_embedding AS vector)
                LIMIT :top_k
                """
            ),
            {
                "query_embedding": format_embedding_vector(query_embedding),
                "top_k": top_k,
            },
        ).mappings()

        results: list[dict] = []
        for rank, row in enumerate(rows, start=1):
            chunk_text = row.get("chunk_text") or ""
            results.append(
                {
                    "rank": rank,
                    "semantic_score": round(float(row.get("semantic_score") or 0), 4),
                    "title": row.get("title"),
                    "source_type": row.get("source_type"),
                    "country": row.get("country"),
                    "event_type": row.get("event_type"),
                    "url": row.get("url"),
                    "chunk_text": chunk_text,
                    "preview": _preview_text(chunk_text),
                    "chunk_id": row.get("chunk_id"),
                    "source_id": row.get("source_id"),
                }
            )

    return results


def print_results(query: str, results: list[dict]) -> None:
    print(f'Query: "{query}"')
    print(f"Results: {len(results)}")
    print("-" * 72)

    if not results:
        print("No semantic matches found. Run `python -m rag.embed_chunks` first.")
        return

    for result in results:
        print(f"Rank: {result.get('rank')}")
        print(f"Semantic score: {result.get('semantic_score', 0)}")
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
        query = "Philippines earthquake water food medical needs"

    try:
        results = semantic_retrieve_context(query)
    except RuntimeError as exc:
        print(exc)
        sys.exit(1)
    except Exception as exc:
        print(f"Semantic retrieval failed: {exc}")
        sys.exit(1)

    print_results(query, results)


if __name__ == "__main__":
    main()
