"""
Project health check for Crisis Resource Intelligence Network.

Verifies PostgreSQL, FastAPI, RAG context, and optional Ollama AI briefing.

Run: python -m scripts.health_check
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=True, encoding="utf-8-sig")

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8001")
REQUEST_TIMEOUT = 10
AI_BRIEFING_TIMEOUT = 180


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


def get_database_url() -> str | None:
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

    return None


def print_ok(message: str) -> None:
    print(f"[OK] {message}")


def print_fail(message: str, detail: str = "") -> None:
    if detail:
        print(f"[FAIL] {message}: {detail}")
    else:
        print(f"[FAIL] {message}")


def print_warn(message: str, detail: str = "") -> None:
    if detail:
        print(f"[WARN] {message}: {detail}")
    else:
        print(f"[WARN] {message}")


def check_database_connection() -> bool:
    database_url = get_database_url()
    if not database_url:
        print_fail("Database connection", "DATABASE_URL not found in .env")
        return False

    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print_ok("Database connection")
        return True
    except Exception as exc:
        print_fail("Database connection", str(exc))
        return False


def check_http_endpoint(
    label: str,
    path: str,
    *,
    timeout: int = REQUEST_TIMEOUT,
    optional: bool = False,
    optional_warn_detail: str = "",
) -> bool:
    url = f"{API_BASE_URL.rstrip('/')}{path}"
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200:
            print_ok(label)
            return True

        detail = f"HTTP {response.status_code}"
        try:
            payload = response.json()
            if isinstance(payload, dict) and payload.get("detail"):
                detail = str(payload["detail"])
        except ValueError:
            pass

        if optional:
            print_warn(label, optional_warn_detail or detail)
            return True

        print_fail(label, detail)
        return False
    except requests.RequestException as exc:
        if optional:
            print_warn(label, optional_warn_detail or str(exc))
            return True

        print_fail(label, str(exc))
        return False
    except Exception as exc:
        if optional:
            print_warn(label, optional_warn_detail or str(exc))
            return True

        print_fail(label, str(exc))
        return False


def main() -> None:
    required_ok = True

    if not check_database_connection():
        required_ok = False

    if not check_http_endpoint("FastAPI backend", "/"):
        required_ok = False

    if not check_http_endpoint(
        "RAG context endpoint",
        "/reports/rag-zone-context/ZONE001",
    ):
        required_ok = False

    check_http_endpoint(
        "AI briefing endpoint",
        "/reports/ai-zone-briefing/ZONE001",
        timeout=AI_BRIEFING_TIMEOUT,
        optional=True,
        optional_warn_detail="Ollama may not be running",
    )

    sys.exit(0 if required_ok else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print_fail("Health check", str(exc))
        sys.exit(1)
