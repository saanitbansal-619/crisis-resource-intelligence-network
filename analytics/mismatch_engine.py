"""
Supply-demand mismatch engine.

Compares resource inventory against requests by zone and resource type,
calculates shortage metrics, and upserts results into mismatch_scores.

Run: python -m analytics.mismatch_engine
"""

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.sql"

load_dotenv(dotenv_path=ENV_PATH, override=True, encoding="utf-8-sig")

URGENCY_WEIGHTS = {
    "low": 1.0,
    "medium": 1.5,
    "high": 2.0,
    "critical": 3.0,
}

WEIGHT_TO_URGENCY = {weight: level for level, weight in URGENCY_WEIGHTS.items()}


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
    """Execute schema.sql to ensure all tables exist."""
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(schema_sql))


def _max_urgency_level(levels: pd.Series) -> str | None:
    """Return the highest urgency level from a series of request urgency values."""
    valid = [level for level in levels.dropna() if level in URGENCY_WEIGHTS]
    if not valid:
        return None
    return max(valid, key=lambda level: URGENCY_WEIGHTS[level])


def classify_status(shortage_gap: int, shortage_ratio: float) -> str:
    """Assign an operational status label based on gap and ratio."""
    if shortage_gap <= -100:
        return "surplus"
    if shortage_gap <= 0:
        return "stable"
    if shortage_ratio < 0.25:
        return "moderate shortage"
    if shortage_ratio < 0.60:
        return "severe shortage"
    return "critical shortage"


def calculate_mismatches(inventory_df: pd.DataFrame, requests_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate supply/demand and compute mismatch metrics."""
    supply = (
        inventory_df.groupby(["zone_id", "resource_type"], as_index=False)["quantity_available"]
        .sum()
        .rename(columns={"quantity_available": "total_available"})
    )

    demand = (
        requests_df.groupby(["zone_id", "resource_type"], as_index=False)
        .agg(
            total_needed=("quantity_needed", "sum"),
            urgency_level=("urgency_level", _max_urgency_level),
        )
    )

    merged = pd.merge(supply, demand, on=["zone_id", "resource_type"], how="outer")
    merged["total_available"] = merged["total_available"].fillna(0).astype(int)
    merged["total_needed"] = merged["total_needed"].fillna(0).astype(int)

    merged["shortage_gap"] = merged["total_needed"] - merged["total_available"]
    merged["shortage_ratio"] = merged.apply(
        lambda row: row["shortage_gap"] / row["total_needed"] if row["total_needed"] > 0 else 0.0,
        axis=1,
    )

    merged["urgency_weight"] = merged["urgency_level"].map(URGENCY_WEIGHTS).fillna(1.0)
    merged["mismatch_score"] = merged["shortage_gap"] * merged["urgency_weight"]
    merged["status_label"] = merged.apply(
        lambda row: classify_status(row["shortage_gap"], row["shortage_ratio"]),
        axis=1,
    )
    merged["mismatch_id"] = merged["zone_id"] + "_" + merged["resource_type"]

    return merged[
        [
            "mismatch_id",
            "zone_id",
            "resource_type",
            "total_available",
            "total_needed",
            "shortage_gap",
            "shortage_ratio",
            "urgency_level",
            "urgency_weight",
            "mismatch_score",
            "status_label",
        ]
    ]


def upsert_mismatch_scores(conn, df: pd.DataFrame) -> tuple[int, int]:
    """Upsert mismatch score rows into PostgreSQL."""
    if df.empty:
        return 0, 0

    existing = {
        str(row[0])
        for row in conn.execute(text("SELECT mismatch_id FROM mismatch_scores")).fetchall()
    }

    upsert_sql = text(
        """
        INSERT INTO mismatch_scores (
            mismatch_id, zone_id, resource_type, total_available, total_needed,
            shortage_gap, shortage_ratio, urgency_level, urgency_weight,
            mismatch_score, status_label
        ) VALUES (
            :mismatch_id, :zone_id, :resource_type, :total_available, :total_needed,
            :shortage_gap, :shortage_ratio, :urgency_level, :urgency_weight,
            :mismatch_score, :status_label
        )
        ON CONFLICT (mismatch_id) DO UPDATE SET
            zone_id = EXCLUDED.zone_id,
            resource_type = EXCLUDED.resource_type,
            total_available = EXCLUDED.total_available,
            total_needed = EXCLUDED.total_needed,
            shortage_gap = EXCLUDED.shortage_gap,
            shortage_ratio = EXCLUDED.shortage_ratio,
            urgency_level = EXCLUDED.urgency_level,
            urgency_weight = EXCLUDED.urgency_weight,
            mismatch_score = EXCLUDED.mismatch_score,
            status_label = EXCLUDED.status_label,
            calculated_at = CURRENT_TIMESTAMP
        """
    )

    records = df.to_dict(orient="records")
    conn.execute(upsert_sql, records)

    inserted = sum(1 for record in records if record["mismatch_id"] not in existing)
    return inserted, len(records) - inserted


def print_top_shortages(conn) -> None:
    """Print top 10 critical/severe shortages by mismatch score."""
    query = text(
        """
        SELECT m.zone_id, z.zone_name, m.resource_type, m.total_available,
               m.total_needed, m.shortage_gap, m.urgency_level,
               m.mismatch_score, m.status_label
        FROM mismatch_scores m
        JOIN zones z ON m.zone_id = z.zone_id
        WHERE m.status_label IN ('critical shortage', 'severe shortage')
        ORDER BY m.mismatch_score DESC
        LIMIT 10
        """
    )
    rows = conn.execute(query).mappings().all()

    print("\nTop 10 critical/severe shortages:")
    if not rows:
        print("  (none)")
        return

    preview = pd.DataFrame(rows)
    print(preview.to_string(index=False))


def print_top_surplus(conn) -> None:
    """Print top 10 surplus resources by shortage gap ascending."""
    query = text(
        """
        SELECT m.zone_id, z.zone_name, m.resource_type, m.total_available,
               m.total_needed, m.shortage_gap, m.status_label
        FROM mismatch_scores m
        JOIN zones z ON m.zone_id = z.zone_id
        WHERE m.status_label = 'surplus'
        ORDER BY m.shortage_gap ASC
        LIMIT 10
        """
    )
    rows = conn.execute(query).mappings().all()

    print("\nTop 10 surplus resources:")
    if not rows:
        print("  (none)")
        return

    preview = pd.DataFrame(rows)
    print(preview.to_string(index=False))


def main() -> None:
    engine = create_engine(get_database_url())
    init_schema(engine)

    with engine.connect() as conn:
        inventory_df = pd.read_sql("SELECT * FROM resource_inventory", conn)
        requests_df = pd.read_sql("SELECT * FROM resource_requests", conn)

    mismatches_df = calculate_mismatches(inventory_df, requests_df)

    with engine.begin() as conn:
        inserted, updated = upsert_mismatch_scores(conn, mismatches_df)

    print(f"mismatch_scores: {inserted} inserted, {updated} updated")

    with engine.connect() as conn:
        print_top_shortages(conn)
        print_top_surplus(conn)


if __name__ == "__main__":
    main()
