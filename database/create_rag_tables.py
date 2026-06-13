"""
Create PostgreSQL tables and indexes for pgvector-backed RAG chunks.

Run: python -m database.create_rag_tables
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

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


def create_rag_tables(engine) -> list[str]:
    warnings: list[str] = []

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS rag_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    doc_id TEXT,
                    source_type TEXT,
                    source_id TEXT,
                    title TEXT,
                    country TEXT,
                    event_type TEXT,
                    published_at TEXT,
                    url TEXT,
                    chunk_index INTEGER,
                    chunk_text TEXT NOT NULL,
                    embedding vector(768),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_rag_chunks_country ON rag_chunks (country)")
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_rag_chunks_source_type ON rag_chunks (source_type)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_rag_chunks_event_type ON rag_chunks (event_type)"
            )
        )

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding
                    ON rag_chunks
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                    """
                )
            )
    except Exception as exc:
        warnings.append(
            "Vector IVFFlat index was not created. "
            f"This is expected on an empty table or before embeddings are loaded. Details: {exc}"
        )

    return warnings


def main() -> None:
    engine = create_engine(get_database_url())
    warnings = create_rag_tables(engine)

    print("pgvector enabled")
    print("rag_chunks table ready")
    if warnings:
        print("Index warnings:")
        for warning in warnings:
            print(f"- {warning}")
    else:
        print("indexes created")


if __name__ == "__main__":
    main()
