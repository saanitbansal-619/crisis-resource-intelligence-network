"""
Load simulated humanitarian resource data into PostgreSQL.

Creates tables from schema.sql, upserts rows from data/sample/, and prints
load statistics plus row counts for verification.

Run: python -m database.load_resources
"""

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
SAMPLE_DIR = PROJECT_ROOT / "data" / "sample"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

CSV_FILES = {
    "organizations": SAMPLE_DIR / "organizations.csv",
    "zones": SAMPLE_DIR / "zones.csv",
    "resource_inventory": SAMPLE_DIR / "resource_inventory.csv",
    "resource_requests": SAMPLE_DIR / "resource_requests.csv",
}

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
    """Read DATABASE_URL from .env, falling back to POSTGRES_* variables."""
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


def _parse_timestamp_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Parse a CSV timestamp column into naive UTC datetimes for PostgreSQL."""
    if column not in df.columns:
        return df
    parsed = pd.to_datetime(df[column], errors="coerce", utc=True)
    df[column] = parsed.dt.tz_convert(None)
    return df


def upsert_organizations(conn, df: pd.DataFrame) -> tuple[int, int]:
    """Upsert organization rows."""
    if df.empty:
        return 0, 0

    existing = _existing_ids(conn, "organizations", "org_id")
    sql = text(
        """
        INSERT INTO organizations (org_id, org_name, org_type, country, contact_email)
        VALUES (:org_id, :org_name, :org_type, :country, :contact_email)
        ON CONFLICT (org_id) DO UPDATE SET
            org_name = EXCLUDED.org_name,
            org_type = EXCLUDED.org_type,
            country = EXCLUDED.country,
            contact_email = EXCLUDED.contact_email
        """
    )
    records = _prepare_records(df)
    conn.execute(sql, records)
    inserted = sum(1 for record in records if record["org_id"] not in existing)
    return inserted, len(records) - inserted


def upsert_zones(conn, df: pd.DataFrame) -> tuple[int, int]:
    """Upsert zone rows."""
    if df.empty:
        return 0, 0

    existing = _existing_ids(conn, "zones", "zone_id")
    sql = text(
        """
        INSERT INTO zones (
            zone_id, zone_name, country, admin_region, latitude, longitude,
            population_estimate, crisis_event_id
        ) VALUES (
            :zone_id, :zone_name, :country, :admin_region, :latitude, :longitude,
            :population_estimate, :crisis_event_id
        )
        ON CONFLICT (zone_id) DO UPDATE SET
            zone_name = EXCLUDED.zone_name,
            country = EXCLUDED.country,
            admin_region = EXCLUDED.admin_region,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            population_estimate = EXCLUDED.population_estimate,
            crisis_event_id = EXCLUDED.crisis_event_id
        """
    )
    records = _prepare_records(df)
    conn.execute(sql, records)
    inserted = sum(1 for record in records if record["zone_id"] not in existing)
    return inserted, len(records) - inserted


def upsert_resource_inventory(conn, df: pd.DataFrame) -> tuple[int, int]:
    """Upsert resource inventory rows."""
    if df.empty:
        return 0, 0

    existing = _existing_ids(conn, "resource_inventory", "inventory_id")
    sql = text(
        """
        INSERT INTO resource_inventory (
            inventory_id, org_id, zone_id, resource_type,
            quantity_available, unit, last_updated
        ) VALUES (
            :inventory_id, :org_id, :zone_id, :resource_type,
            :quantity_available, :unit, :last_updated
        )
        ON CONFLICT (inventory_id) DO UPDATE SET
            org_id = EXCLUDED.org_id,
            zone_id = EXCLUDED.zone_id,
            resource_type = EXCLUDED.resource_type,
            quantity_available = EXCLUDED.quantity_available,
            unit = EXCLUDED.unit,
            last_updated = EXCLUDED.last_updated
        """
    )
    records = _prepare_records(df)
    conn.execute(sql, records)
    inserted = sum(1 for record in records if record["inventory_id"] not in existing)
    return inserted, len(records) - inserted


def upsert_resource_requests(conn, df: pd.DataFrame) -> tuple[int, int]:
    """Upsert resource request rows."""
    if df.empty:
        return 0, 0

    existing = _existing_ids(conn, "resource_requests", "request_id")
    sql = text(
        """
        INSERT INTO resource_requests (
            request_id, zone_id, resource_type, quantity_needed,
            urgency_level, requested_by, request_timestamp
        ) VALUES (
            :request_id, :zone_id, :resource_type, :quantity_needed,
            :urgency_level, :requested_by, :request_timestamp
        )
        ON CONFLICT (request_id) DO UPDATE SET
            zone_id = EXCLUDED.zone_id,
            resource_type = EXCLUDED.resource_type,
            quantity_needed = EXCLUDED.quantity_needed,
            urgency_level = EXCLUDED.urgency_level,
            requested_by = EXCLUDED.requested_by,
            request_timestamp = EXCLUDED.request_timestamp
        """
    )
    records = _prepare_records(df)
    conn.execute(sql, records)
    inserted = sum(1 for record in records if record["request_id"] not in existing)
    return inserted, len(records) - inserted


def main() -> None:
    for table_name, csv_path in CSV_FILES.items():
        if not csv_path.exists():
            print(f"Missing sample file: {csv_path}")
            print("Run: python -m database.generate_sample_resources")
            return

    database_url = get_database_url()
    print(f"Loaded DATABASE_URL: {mask_database_url(database_url)}")

    engine = create_engine(database_url)
    init_schema(engine)

    orgs_df = pd.read_csv(CSV_FILES["organizations"])
    zones_df = pd.read_csv(CSV_FILES["zones"])
    inventory_df = pd.read_csv(CSV_FILES["resource_inventory"])
    requests_df = pd.read_csv(CSV_FILES["resource_requests"])

    inventory_df = _parse_timestamp_column(inventory_df, "last_updated")
    requests_df = _parse_timestamp_column(requests_df, "request_timestamp")

    with engine.begin() as conn:
        org_ins, org_upd = upsert_organizations(conn, orgs_df)
        zone_ins, zone_upd = upsert_zones(conn, zones_df)
        inv_ins, inv_upd = upsert_resource_inventory(conn, inventory_df)
        req_ins, req_upd = upsert_resource_requests(conn, requests_df)

        org_count = conn.execute(text("SELECT COUNT(*) FROM organizations")).scalar_one()
        zone_count = conn.execute(text("SELECT COUNT(*) FROM zones")).scalar_one()
        inv_count = conn.execute(text("SELECT COUNT(*) FROM resource_inventory")).scalar_one()
        req_count = conn.execute(text("SELECT COUNT(*) FROM resource_requests")).scalar_one()

    print("Schema applied from database/schema.sql")
    print(f"organizations: {org_ins} inserted, {org_upd} updated")
    print(f"zones: {zone_ins} inserted, {zone_upd} updated")
    print(f"resource_inventory: {inv_ins} inserted, {inv_upd} updated")
    print(f"resource_requests: {req_ins} inserted, {req_upd} updated")
    print(f"Test query — organizations row count: {org_count}")
    print(f"Test query — zones row count: {zone_count}")
    print(f"Test query — resource_inventory row count: {inv_count}")
    print(f"Test query — resource_requests row count: {req_count}")


if __name__ == "__main__":
    main()
