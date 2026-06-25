"""
Build shortage-risk ML features and transparent proxy labels.

Feature engineering and proxy-label creation are implemented as pure functions
so they can be unit-tested without a database. Labels are *simulated/proxy*
operational labels derived transparently from shortage gap, fulfillment ratio,
urgency, mismatch score, and resource criticality, because real NGO
demand-outcome labels are not publicly available.

Run: python -m ml_forecasting.feature_builder
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

CATEGORICAL_FEATURES = ["crisis_type", "country", "resource_type"]
NUMERIC_FEATURES = [
    "shortage_gap",
    "request_quantity",
    "available_quantity",
    "fulfillment_ratio",
    "urgency_score",
    "mismatch_score",
    "gdacs_alert_count",
    "report_count",
]
FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES
LABEL_COLUMN = "shortage_risk_level"
IDENTITY_COLUMNS = ["zone_id", "zone_name", "country", "resource_type"]

RISK_LEVELS = ["low", "medium", "high", "critical"]

URGENCY_SCORES = {"low": 1, "medium": 2, "high": 3, "critical": 4}

# Resource types where shortages are life-critical and escalate risk faster.
CRITICAL_RESOURCE_TYPES = frozenset(
    {
        "insulin",
        "antibiotics",
        "medicine",
        "medical_staff",
        "water_kits",
        "water",
    }
)

# Mismatch score (shortage gap x urgency weight) above which pressure is "high".
HIGH_MISMATCH_THRESHOLD = 500.0

PROXY_LABEL_NOTE = (
    "shortage_risk_level is a simulated/proxy operational label derived from "
    "shortage gap, fulfillment ratio, urgency, mismatch score, and resource "
    "criticality. Real NGO demand-outcome labels are not publicly available."
)

FEATURE_NOTE = (
    "Features are built from crisis/resource/mismatch records: country, zone, "
    "resource type, requested vs. available quantity, shortage gap, fulfillment "
    "ratio, urgency score, mismatch score, derived crisis type, and country-level "
    "GDACS alert and ReliefWeb report counts. Missing values use safe defaults "
    "(crisis_type='unknown', counts=0, urgency='low')."
)

# Shared SQL used for both training-data construction and live forecasting.
# Aggregated crisis-context counts are matched by country. On databases that do
# not contain the gdacs/crisis tables (e.g. a CI placeholder), this query will
# fail and callers degrade gracefully.
FEATURE_QUERY = """
    SELECT
        m.zone_id,
        z.zone_name,
        z.country,
        m.resource_type,
        m.total_available AS available_quantity,
        m.total_needed AS request_quantity,
        m.shortage_gap,
        m.shortage_ratio,
        m.urgency_level,
        m.mismatch_score,
        COALESCE((
            SELECT ga.event_type
            FROM gdacs_alerts ga
            WHERE ga.country = z.country AND ga.event_type IS NOT NULL
            ORDER BY ga.pub_date_parsed DESC NULLS LAST
            LIMIT 1
        ), 'unknown') AS crisis_type,
        (SELECT COUNT(*) FROM gdacs_alerts ga WHERE ga.country = z.country)
            AS gdacs_alert_count,
        (SELECT COUNT(*) FROM crisis_reports cr WHERE cr.primary_country = z.country)
            AS report_count
    FROM mismatch_scores m
    JOIN zones z ON m.zone_id = z.zone_id
"""


def _to_int(value, default: int = 0) -> int:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value, default: float = 0.0) -> float:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean_text(value, default: str = "unknown") -> str:
    text = ("" if value is None else str(value)).strip()
    return text if text else default


def compute_fulfillment_ratio(available_quantity, request_quantity) -> float:
    """Return available/requested, clamped to [0, 1]. No demand -> fully met."""
    needed = _to_float(request_quantity)
    available = _to_float(available_quantity)
    if needed <= 0:
        return 1.0
    return max(0.0, min(1.0, available / needed))


def urgency_to_score(urgency_level) -> int:
    """Map an urgency label to an ordinal score (low=1 ... critical=4)."""
    return URGENCY_SCORES.get(_clean_text(urgency_level, "low").lower(), 1)


def is_critical_resource(resource_type) -> bool:
    """Return True for life-critical resource types."""
    return _clean_text(resource_type, "").lower() in CRITICAL_RESOURCE_TYPES


def assign_proxy_risk_level(
    shortage_gap,
    fulfillment_ratio: float,
    urgency_score: int,
    mismatch_score,
    resource_type: str | None = None,
) -> str:
    """Interpretable rule-based proxy label for shortage severity risk.

    This is NOT a real operational outcome. It encodes a simple, explainable
    severity heuristic so a baseline classifier has something to learn:

    - critical: fulfillment_ratio < 0.25 with high pressure (mismatch/urgency) or
      a life-critical resource
    - high:     fulfillment_ratio < 0.50 (or a critical resource under pressure)
    - medium:   fulfillment_ratio < 0.80
    - low:      otherwise (including no active shortage)
    """
    gap = _to_int(shortage_gap)
    if gap <= 0:
        return "low"

    ratio = _to_float(fulfillment_ratio, 1.0)
    high_pressure = (
        _to_float(mismatch_score) >= HIGH_MISMATCH_THRESHOLD or int(urgency_score) >= 3
    )
    critical_resource = is_critical_resource(resource_type)

    if ratio < 0.25 and (high_pressure or critical_resource):
        return "critical"
    if ratio < 0.50 and critical_resource and high_pressure:
        return "critical"
    if ratio < 0.50:
        return "high"
    if ratio < 0.80:
        return "medium"
    return "low"


def build_raw_records(rows: list[dict]) -> list[dict]:
    """Normalize raw DB rows into a stable raw-record shape for feature building."""
    records: list[dict] = []
    for row in rows:
        records.append(
            {
                "zone_id": _clean_text(row.get("zone_id"), ""),
                "zone_name": _clean_text(row.get("zone_name"), "Unknown Zone"),
                "country": _clean_text(row.get("country"), "unknown"),
                "resource_type": _clean_text(row.get("resource_type"), "unknown"),
                "crisis_type": _clean_text(row.get("crisis_type"), "unknown"),
                "available_quantity": _to_int(row.get("available_quantity")),
                "request_quantity": _to_int(row.get("request_quantity")),
                "shortage_gap": _to_int(row.get("shortage_gap")),
                "urgency_level": _clean_text(row.get("urgency_level"), "low"),
                "mismatch_score": _to_float(row.get("mismatch_score")),
                "gdacs_alert_count": _to_int(row.get("gdacs_alert_count")),
                "report_count": _to_int(row.get("report_count")),
            }
        )
    return records


def build_feature_frame(records: list[dict], include_label: bool = True) -> pd.DataFrame:
    """Build a model-ready DataFrame (features + identity, optional proxy label)."""
    rows: list[dict] = []
    for record in records:
        fulfillment_ratio = compute_fulfillment_ratio(
            record.get("available_quantity"),
            record.get("request_quantity"),
        )
        urgency_score = urgency_to_score(record.get("urgency_level"))
        resource_type = _clean_text(record.get("resource_type"), "unknown")

        feature_row = {
            "zone_id": record.get("zone_id", ""),
            "zone_name": record.get("zone_name", "Unknown Zone"),
            "crisis_type": _clean_text(record.get("crisis_type"), "unknown"),
            "country": _clean_text(record.get("country"), "unknown"),
            "resource_type": resource_type,
            "shortage_gap": _to_int(record.get("shortage_gap")),
            "request_quantity": _to_int(record.get("request_quantity")),
            "available_quantity": _to_int(record.get("available_quantity")),
            "fulfillment_ratio": round(fulfillment_ratio, 4),
            "urgency_score": urgency_score,
            "mismatch_score": _to_float(record.get("mismatch_score")),
            "gdacs_alert_count": _to_int(record.get("gdacs_alert_count")),
            "report_count": _to_int(record.get("report_count")),
        }

        if include_label:
            feature_row[LABEL_COLUMN] = assign_proxy_risk_level(
                feature_row["shortage_gap"],
                feature_row["fulfillment_ratio"],
                feature_row["urgency_score"],
                feature_row["mismatch_score"],
                resource_type=resource_type,
            )

        rows.append(feature_row)

    columns = ["zone_id", "zone_name"] + FEATURE_COLUMNS
    if include_label:
        columns = columns + [LABEL_COLUMN]
    seen: set[str] = set()
    ordered_columns = [c for c in columns if not (c in seen or seen.add(c))]

    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=ordered_columns)
    return frame[[c for c in ordered_columns if c in frame.columns]]


def get_database_url() -> str | None:
    """Read DATABASE_URL without exiting the process when it is missing."""
    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=ENV_PATH, override=False, encoding="utf-8-sig")
    except Exception:
        pass

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    if ENV_PATH.exists():
        with ENV_PATH.open(encoding="utf-8-sig") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped.startswith("DATABASE_URL="):
                    return stripped.split("=", 1)[1].strip()
    return None


def load_feature_records_from_db() -> list[dict]:
    """Load raw feature records from PostgreSQL using the shared FEATURE_QUERY."""
    from sqlalchemy import create_engine, text

    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured; cannot build training data.")

    engine = create_engine(database_url)
    with engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(text(FEATURE_QUERY)).mappings()]
    return build_raw_records(rows)


def build_training_data() -> pd.DataFrame:
    """Build the labeled training DataFrame from the database."""
    records = load_feature_records_from_db()
    return build_feature_frame(records, include_label=True)


def main() -> None:
    frame = build_training_data()
    print(f"Training rows: {len(frame)}")
    if frame.empty:
        print("No training data available. Run ingestion and mismatch scoring first.")
        return
    print("\nLabel distribution (simulated/proxy labels):")
    print(frame[LABEL_COLUMN].value_counts().to_string())
    print(f"\n{PROXY_LABEL_NOTE}")


if __name__ == "__main__":
    main()
