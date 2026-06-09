"""
Database connection and session management for the FastAPI backend.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=True, encoding="utf-8-sig")


def mask_database_url(url: str) -> str:
    """Mask the password in a database URL for safe logging."""
    if "://" not in url or "@" not in url:
        return url

    scheme, remainder = url.split("://", 1)
    credentials, host_part = remainder.rsplit("@", 1)

    if ":" in credentials:
        username, _ = credentials.split(":", 1)
        return f"{scheme}://{username}:***@{host_part}"

    return url


def _parse_database_url_manual(env_path: Path) -> str | None:
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
    """Read DATABASE_URL from environment variables."""
    database_url = os.getenv("DATABASE_URL") or _parse_database_url_manual(ENV_PATH)
    if database_url:
        return database_url

    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT")
    db = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")

    if all([host, port, db, user, password]):
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"

    print(
        "DATABASE_URL not found. Create a .env file in the project root using .env.example."
    )
    print(f"Expected .env path: {ENV_PATH}")
    sys.exit(1)


engine = create_engine(get_database_url())
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def rows_to_dicts(result) -> list[dict]:
    """Convert SQLAlchemy result rows to JSON-serializable dictionaries."""
    return [dict(row._mapping) for row in result]


def row_to_dict(result) -> dict | None:
    """Convert a single SQLAlchemy result row to a dictionary."""
    row = result.first()
    if row is None:
        return None
    return dict(row._mapping)


def check_database_connection() -> bool:
    """Return True if the database accepts connections."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
