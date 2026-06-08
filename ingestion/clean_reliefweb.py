"""
ReliefWeb data cleaning and normalization.

Reads the most recent raw ReliefWeb JSON from data/raw/, normalizes report
metadata into a flat table, and writes a processed CSV for downstream loading.

Run: python -m ingestion.clean_reliefweb
"""

import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_FILE = PROCESSED_DATA_DIR / "reliefweb_reports_clean.csv"

OUTPUT_COLUMNS = [
    "reliefweb_id",
    "title",
    "countries",
    "primary_country",
    "date_original",
    "date_parsed",
    "source_name",
    "source_type",
    "disaster_types",
    "themes",
    "language",
    "url",
    "body_text",
]


def find_latest_raw_file() -> Path | None:
    """Return the most recent reliefweb_reports_*.json file in data/raw/."""
    candidates = sorted(
        RAW_DATA_DIR.glob("reliefweb_reports_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _names_from_list(items: list | None, key: str = "name") -> str:
    """Join name fields from a list of dicts into a comma-separated string."""
    if not items or not isinstance(items, list):
        return ""
    names = [item.get(key, "") for item in items if isinstance(item, dict)]
    return ", ".join(name for name in names if name)


def _extract_source(fields: dict) -> tuple[str, str]:
    """Extract source_name and source_type from list or dict source field."""
    source = fields.get("source")
    if isinstance(source, list) and source:
        source = source[0]
    if not isinstance(source, dict):
        return "", ""

    source_name = source.get("name", "") or ""
    source_type_field = source.get("type")
    if isinstance(source_type_field, dict):
        source_type = source_type_field.get("name", "") or ""
    elif isinstance(source_type_field, list) and source_type_field:
        first_type = source_type_field[0]
        source_type = first_type.get("name", "") if isinstance(first_type, dict) else str(first_type)
    else:
        source_type = str(source_type_field) if source_type_field else ""

    return source_name, source_type


def _extract_language(fields: dict) -> str:
    """Extract language as a comma-separated string."""
    language = fields.get("language")
    if isinstance(language, list):
        return _names_from_list(language)
    if isinstance(language, dict):
        return language.get("name", "") or ""
    if isinstance(language, str):
        return language
    return ""


def normalize_record(item: dict) -> dict:
    """Normalize a single ReliefWeb report record."""
    fields = item.get("fields", {})
    countries_list = fields.get("country", [])
    country_names = [
        country.get("name", "")
        for country in countries_list
        if isinstance(country, dict) and country.get("name")
    ]

    source_name, source_type = _extract_source(fields)
    date_original = fields.get("date", {}).get("original") if isinstance(fields.get("date"), dict) else None

    return {
        "reliefweb_id": item.get("id"),
        "title": fields.get("title") or fields.get("headline") or "",
        "countries": ", ".join(country_names),
        "primary_country": country_names[0] if country_names else "",
        "date_original": date_original or "",
        "date_parsed": pd.to_datetime(date_original, errors="coerce") if date_original else pd.NaT,
        "source_name": source_name,
        "source_type": source_type,
        "disaster_types": _names_from_list(fields.get("disaster_type")),
        "themes": _names_from_list(fields.get("theme")),
        "language": _extract_language(fields),
        "url": fields.get("url") or "",
        "body_text": fields.get("body") or "",
    }


def load_and_clean(raw_path: Path) -> pd.DataFrame:
    """Load raw JSON and return a normalized DataFrame."""
    with raw_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    records = [normalize_record(item) for item in payload.get("data", [])]
    df = pd.DataFrame(records, columns=OUTPUT_COLUMNS)
    return df


def main() -> None:
    raw_path = find_latest_raw_file()
    if raw_path is None:
        print("No ReliefWeb raw file found in data/raw/.")
        print("Run: python -m ingestion.reliefweb_ingest")
        return

    print(f"Loaded raw file: {raw_path}")
    df = load_and_clean(raw_path)

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"Cleaned {len(df)} records.")
    print(f"Saved processed CSV to: {OUTPUT_FILE}")

    if not df.empty:
        preview = df.head().copy()
        preview["body_text"] = preview["body_text"].str.slice(0, 80) + "..."
        print(preview.to_string(index=False))


if __name__ == "__main__":
    main()
