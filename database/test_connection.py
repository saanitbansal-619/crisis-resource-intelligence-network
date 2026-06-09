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


def mask_env_line(line: str) -> str:
    """Mask sensitive values in an .env line for debug output."""
    upper = line.upper()
    if "PASSWORD" in upper or "APPNAME" in upper:
        key, _, _ = line.partition("=")
        return f"{key}=***"
    return line


def print_env_debug() -> None:
    """Print debug information about the .env file before failing."""
    print(f"ENV_PATH exists: {ENV_PATH.exists()}")
    print(f"ENV_PATH: {ENV_PATH}")

    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8-sig").splitlines()
        non_empty = [line.strip() for line in lines if line.strip()]
        print("First 5 non-empty .env lines:")
        for line in non_empty[:5]:
            print(f"  {mask_env_line(line)}")

    print(f"DATABASE_URL in os.environ after load_dotenv: {'DATABASE_URL' in os.environ}")


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


def main() -> None:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print_env_debug()

        database_url = parse_database_url_manual(ENV_PATH)
        if database_url:
            print("Loaded DATABASE_URL using manual fallback parser")
        else:
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
