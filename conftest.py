"""Shared pytest configuration and helpers.

Ensures the project root is importable and provides graceful database
availability checks so DB-backed tests can skip when PostgreSQL or sample
data is unavailable (e.g. CI without a database).
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def database_available() -> bool:
    """Return True only when PostgreSQL accepts connections."""
    try:
        from backend.database import check_database_connection

        return bool(check_database_connection())
    except Exception:
        return False
