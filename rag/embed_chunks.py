"""
Embed RAG chunks with Ollama nomic-embed-text and store vectors in PostgreSQL.

Run: python -m rag.embed_chunks
     python -m rag.embed_chunks --force
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
CHUNKS_PATH = PROJECT_ROOT / "data" / "rag" / "chunks.json"

OLLAMA_EMBEDDINGS_URL = "http://localhost:11434/api/embeddings"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
EMBEDDING_MODEL = "nomic-embed-text"
PROGRESS_INTERVAL = 5

OLLAMA_UNAVAILABLE_MESSAGE = (
    "Ollama is not running. Start Ollama and make sure `ollama list` shows nomic-embed-text."
)

UPSERT_SQL = """
INSERT INTO rag_chunks (
    chunk_id,
    doc_id,
    source_type,
    source_id,
    title,
    country,
    event_type,
    published_at,
    url,
    chunk_index,
    chunk_text,
    embedding
) VALUES (
    :chunk_id,
    :doc_id,
    :source_type,
    :source_id,
    :title,
    :country,
    :event_type,
    :published_at,
    :url,
    :chunk_index,
    :chunk_text,
    CAST(:embedding AS vector)
)
ON CONFLICT (chunk_id) DO UPDATE SET
    doc_id = EXCLUDED.doc_id,
    source_type = EXCLUDED.source_type,
    source_id = EXCLUDED.source_id,
    title = EXCLUDED.title,
    country = EXCLUDED.country,
    event_type = EXCLUDED.event_type,
    published_at = EXCLUDED.published_at,
    url = EXCLUDED.url,
    chunk_index = EXCLUDED.chunk_index,
    chunk_text = EXCLUDED.chunk_text,
    embedding = EXCLUDED.embedding
"""

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
        print(
            "DATABASE_URL not found. Create a .env file in the project root using .env.example."
        )
        print(f"Expected .env path: {ENV_PATH}")
        sys.exit(1)
    return database_url


def load_chunks(path: Path = CHUNKS_PATH) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"Chunks file not found: {path}. Run `python -m rag.chunk_documents` first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def format_embedding_vector(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def ensure_ollama_ready() -> None:
    try:
        response = requests.get(OLLAMA_TAGS_URL, timeout=5)
        response.raise_for_status()
        models = response.json().get("models", [])
        model_names = {model.get("name", "").split(":")[0] for model in models}
        if EMBEDDING_MODEL not in model_names and not any(
            name.startswith(EMBEDDING_MODEL) for name in model_names
        ):
            print(
                f"Ollama is running, but model `{EMBEDDING_MODEL}` was not found. "
                f"Run: ollama pull {EMBEDDING_MODEL}"
            )
            sys.exit(1)
    except requests.RequestException as exc:
        print(OLLAMA_UNAVAILABLE_MESSAGE)
        print(f"Details: {exc}")
        sys.exit(1)


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


def get_embedded_chunk_ids(conn) -> set[str]:
    rows = conn.execute(
        text(
            """
            SELECT chunk_id
            FROM rag_chunks
            WHERE embedding IS NOT NULL
            """
        )
    ).mappings()
    return {row["chunk_id"] for row in rows}


def upsert_chunk(conn, chunk: dict, embedding: list[float]) -> None:
    conn.execute(
        text(UPSERT_SQL),
        {
            "chunk_id": chunk.get("chunk_id"),
            "doc_id": chunk.get("doc_id"),
            "source_type": chunk.get("source_type"),
            "source_id": chunk.get("source_id"),
            "title": chunk.get("title"),
            "country": chunk.get("country"),
            "event_type": chunk.get("event_type"),
            "published_at": chunk.get("published_at"),
            "url": chunk.get("url"),
            "chunk_index": chunk.get("chunk_index"),
            "chunk_text": chunk.get("chunk_text"),
            "embedding": format_embedding_vector(embedding),
        },
    )


def embed_chunks(force: bool = False) -> dict[str, int]:
    chunks = load_chunks()
    if not chunks:
        print("No chunks found to embed.")
        return {"embedded": 0, "skipped": 0, "failed": 0}

    ensure_ollama_ready()
    engine = create_engine(get_database_url())

    embedded = 0
    skipped = 0
    failed = 0

    with engine.begin() as conn:
        existing_ids = set() if force else get_embedded_chunk_ids(conn)

    for index, chunk in enumerate(chunks, start=1):
        chunk_id = chunk.get("chunk_id")
        chunk_text = (chunk.get("chunk_text") or "").strip()

        if not chunk_id or not chunk_text:
            skipped += 1
            continue

        if not force and chunk_id in existing_ids:
            skipped += 1
            if index % PROGRESS_INTERVAL == 0:
                print(f"Progress: {index}/{len(chunks)} processed ({embedded} embedded, {skipped} skipped)")
            continue

        try:
            embedding = get_ollama_embedding(chunk_text)
            with engine.begin() as conn:
                upsert_chunk(conn, chunk, embedding)
            embedded += 1
        except requests.RequestException:
            print(OLLAMA_UNAVAILABLE_MESSAGE)
            sys.exit(1)
        except Exception as exc:
            failed += 1
            print(f"Failed to embed chunk {chunk_id}: {exc}")

        if index % PROGRESS_INTERVAL == 0 or index == len(chunks):
            print(f"Progress: {index}/{len(chunks)} processed ({embedded} embedded, {skipped} skipped)")

    return {"embedded": embedded, "skipped": skipped, "failed": failed}


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed RAG chunks into PostgreSQL with Ollama.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-embed all chunks even if embeddings already exist.",
    )
    args = parser.parse_args()

    totals = embed_chunks(force=args.force)
    print("Embedding complete.")
    print(f"Embedded: {totals['embedded']}")
    print(f"Skipped: {totals['skipped']}")
    print(f"Failed: {totals['failed']}")


if __name__ == "__main__":
    main()
