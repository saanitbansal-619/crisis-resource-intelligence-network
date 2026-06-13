"""
Verify that the pgvector extension is available and installed.

Run: python -m database.check_pgvector
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=True, encoding="utf-8-sig")

PGVECTOR_UNAVAILABLE_MESSAGE = (
    "pgvector extension is not available in this Postgres image. "
    "Make sure docker-compose.yml uses pgvector/pgvector:0.8.1-pg15."
)


def parse_database_url_manual(env_path: Path) -> str | None:
    """Fallback parser for DATABASE_URL when load_dotenv misses it (e.g. BOM)."""
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


def main() -> None:
    engine = create_engine(get_database_url())

    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

            row = conn.execute(
                text(
                    """
                    SELECT extname
                    FROM pg_extension
                    WHERE extname = 'vector'
                    """
                )
            ).mappings().one_or_none()
    except Exception as exc:
        print(PGVECTOR_UNAVAILABLE_MESSAGE)
        print(f"Details: {exc}")
        sys.exit(1)

    if row is None:
        print(PGVECTOR_UNAVAILABLE_MESSAGE)
        sys.exit(1)

    print("pgvector extension is installed.")


if __name__ == "__main__":
    main()
