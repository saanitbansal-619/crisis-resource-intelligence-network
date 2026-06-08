"""
Load processed ReliefWeb and GDACS CSVs into PostgreSQL.

Creates tables from schema.sql, upserts rows from data/processed/, and
prints load statistics plus row counts for verification.

Run: python -m database.load_reports
"""

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

RELIEFWEB_CSV = PROCESSED_DIR / "reliefweb_reports_clean.csv"
GDACS_CSV = PROCESSED_DIR / "gdacs_alerts_clean.csv"

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


def get_database_url() -> str:
    """Read DATABASE_URL from .env, falling back to POSTGRES_* variables."""
    database_url = os.getenv("DATABASE_URL")
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


def init_schema(engine) -> None:
    """Execute schema.sql to create tables if they do not exist."""
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(schema_sql))


def _clean_value(value):
    """Convert pandas NaN/NaT values to None for SQL insertion."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if pd.isna(value):
        return None
    return value


def _parse_timestamp_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Parse a CSV timestamp column into naive UTC datetimes for PostgreSQL."""
    if column not in df.columns:
        return df
    parsed = pd.to_datetime(df[column], errors="coerce", utc=True)
    df[column] = parsed.dt.tz_convert(None)
    return df


def _prepare_records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to a list of SQL-ready dict records."""
    records = []
    for row in df.to_dict(orient="records"):
        records.append({key: _clean_value(value) for key, value in row.items()})
    return records


def _existing_ids(conn, table: str, id_column: str) -> set[str]:
    """Return existing primary key values for upsert statistics."""
    rows = conn.execute(text(f"SELECT {id_column} FROM {table}")).fetchall()
    return {str(row[0]) for row in rows}


def upsert_crisis_reports(conn, df: pd.DataFrame) -> tuple[int, int]:
    """Upsert ReliefWeb rows into crisis_reports."""
    if df.empty:
        return 0, 0

    df = df.copy()
    df["reliefweb_id"] = df["reliefweb_id"].astype(str)
    existing = _existing_ids(conn, "crisis_reports", "reliefweb_id")

    upsert_sql = text(
        """
        INSERT INTO crisis_reports (
            reliefweb_id, title, countries, primary_country, date_original,
            date_parsed, source_name, source_type, disaster_types, themes,
            language, url, body_text
        ) VALUES (
            :reliefweb_id, :title, :countries, :primary_country, :date_original,
            :date_parsed, :source_name, :source_type, :disaster_types, :themes,
            :language, :url, :body_text
        )
        ON CONFLICT (reliefweb_id) DO UPDATE SET
            title = EXCLUDED.title,
            countries = EXCLUDED.countries,
            primary_country = EXCLUDED.primary_country,
            date_original = EXCLUDED.date_original,
            date_parsed = EXCLUDED.date_parsed,
            source_name = EXCLUDED.source_name,
            source_type = EXCLUDED.source_type,
            disaster_types = EXCLUDED.disaster_types,
            themes = EXCLUDED.themes,
            language = EXCLUDED.language,
            url = EXCLUDED.url,
            body_text = EXCLUDED.body_text
        """
    )

    records = _prepare_records(df)
    conn.execute(upsert_sql, records)

    inserted = sum(1 for record in records if record["reliefweb_id"] not in existing)
    updated = len(records) - inserted
    return inserted, updated


def upsert_gdacs_alerts(conn, df: pd.DataFrame) -> tuple[int, int]:
    """Upsert GDACS rows into gdacs_alerts."""
    if df.empty:
        return 0, 0

    df = df.copy()
    df["alert_id"] = df["alert_id"].astype(str)
    existing = _existing_ids(conn, "gdacs_alerts", "alert_id")

    upsert_sql = text(
        """
        INSERT INTO gdacs_alerts (
            alert_id, title, event_type, severity_color, country,
            pub_date, pub_date_parsed, description, link
        ) VALUES (
            :alert_id, :title, :event_type, :severity_color, :country,
            :pub_date, :pub_date_parsed, :description, :link
        )
        ON CONFLICT (alert_id) DO UPDATE SET
            title = EXCLUDED.title,
            event_type = EXCLUDED.event_type,
            severity_color = EXCLUDED.severity_color,
            country = EXCLUDED.country,
            pub_date = EXCLUDED.pub_date,
            pub_date_parsed = EXCLUDED.pub_date_parsed,
            description = EXCLUDED.description,
            link = EXCLUDED.link
        """
    )

    records = _prepare_records(df)
    conn.execute(upsert_sql, records)

    inserted = sum(1 for record in records if record["alert_id"] not in existing)
    updated = len(records) - inserted
    return inserted, updated


def main() -> None:
    if not RELIEFWEB_CSV.exists():
        print(f"Missing processed file: {RELIEFWEB_CSV}")
        print("Run: python -m ingestion.clean_reliefweb")
        return

    if not GDACS_CSV.exists():
        print(f"Missing processed file: {GDACS_CSV}")
        print("Run: python -m ingestion.clean_gdacs")
        return

    database_url = get_database_url()
    print(f"Loaded DATABASE_URL: {mask_database_url(database_url)}")

    engine = create_engine(database_url)
    init_schema(engine)

    reliefweb_df = pd.read_csv(RELIEFWEB_CSV)
    gdacs_df = pd.read_csv(GDACS_CSV)

    reliefweb_df = _parse_timestamp_column(reliefweb_df, "date_parsed")
    gdacs_df = _parse_timestamp_column(gdacs_df, "pub_date_parsed")

    with engine.begin() as conn:
        rw_inserted, rw_updated = upsert_crisis_reports(conn, reliefweb_df)
        gd_inserted, gd_updated = upsert_gdacs_alerts(conn, gdacs_df)

        crisis_count = conn.execute(text("SELECT COUNT(*) FROM crisis_reports")).scalar_one()
        gdacs_count = conn.execute(text("SELECT COUNT(*) FROM gdacs_alerts")).scalar_one()

    print("Schema applied from database/schema.sql")
    print(f"crisis_reports: {rw_inserted} inserted, {rw_updated} updated")
    print(f"gdacs_alerts: {gd_inserted} inserted, {gd_updated} updated")
    print(f"Test query — crisis_reports row count: {crisis_count}")
    print(f"Test query — gdacs_alerts row count: {gdacs_count}")


if __name__ == "__main__":
    main()
