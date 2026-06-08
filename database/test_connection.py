"""
Test PostgreSQL database connectivity.

Loads credentials from .env, connects to the local database, and prints
connection status along with the current database name and timestamp.

Run: python -m database.test_connection
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_PATH)


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


def main() -> None:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print(
            "DATABASE_URL not found. Create a .env file in the project root using .env.example."
        )
        print(f"Expected .env path: {ENV_PATH}")
        sys.exit(1)

    print(f"Loaded DATABASE_URL: {mask_database_url(database_url)}")

    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT current_database() AS db_name, CURRENT_TIMESTAMP AS now")
            ).mappings().one()

        print("Database connection successful.")
        print(f"Database: {row['db_name']}")
        print(f"Current timestamp: {row['now']}")
    except Exception:
        print("Database connection failed.")
        print("- Confirm Docker is running.")
        print("- Confirm docker-compose.yml credentials match your .env file.")
        print("- If credentials changed, run: docker compose down -v && docker compose up -d")
        raise


if __name__ == "__main__":
    main()
