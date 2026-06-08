"""
ReliefWeb API ingestion script.

Fetches recent humanitarian reports from the ReliefWeb API, saves raw JSON
to data/raw/, and returns a summary DataFrame for downstream cleaning.

Run: python -m ingestion.reliefweb_ingest
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

# Project root: CrisisResourceIntel/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

# Explicitly load the .env file from the project root
load_dotenv(dotenv_path=ENV_PATH)

RELIEFWEB_API_URL = os.getenv(
    "RELIEFWEB_API_URL",
    "https://api.reliefweb.int/v2/reports",
)

# Do NOT use a fake default appname here.
# If the appname is missing, we want to know immediately.
RELIEFWEB_APPNAME = os.getenv("RELIEFWEB_APPNAME")

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"


def fetch_reliefweb_reports(limit: int = 10) -> dict | None:
    """Fetch recent reports from the ReliefWeb API (v2)."""

    if not RELIEFWEB_APPNAME:
        print("RELIEFWEB_APPNAME was not found.")
        print(f"Expected .env file location: {ENV_PATH}")
        print("Create a .env file in the project root with:")
        print("RELIEFWEB_APPNAME=your_approved_appname_here")
        return None

    print(f"Loaded ReliefWeb appname: {RELIEFWEB_APPNAME[:8]}...")

    params = {
        "appname": RELIEFWEB_APPNAME,
        "profile": "full",
        "limit": limit,
        "sort[]": "date:desc",
    }

    response = requests.get(RELIEFWEB_API_URL, params=params, timeout=30)

    if response.status_code == 403:
        print("ReliefWeb rejected the appname.")
        print("If it was just approved, wait 10–15 minutes and try again.")
        print("Also make sure there are no typos or extra spaces in .env.")
        print(f"Status code: {response.status_code}")
        print(response.text[:500])
        return None

    response.raise_for_status()
    return response.json()


def save_raw_payload(payload: dict) -> Path:
    """Persist the raw API response as timestamped JSON."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = RAW_DATA_DIR / f"reliefweb_reports_{timestamp}.json"

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    return output_path


def payload_to_dataframe(payload: dict) -> pd.DataFrame:
    """Convert ReliefWeb API payload into a flat DataFrame for inspection."""
    records = []

    for item in payload.get("data", []):
        fields = item.get("fields", {})

        source = fields.get("source", {})
        if isinstance(source, list) and source:
            source_name = source[0].get("name")
        elif isinstance(source, dict):
            source_name = source.get("name")
        else:
            source_name = None

        records.append(
            {
                "id": item.get("id"),
                "title": fields.get("title"),
                "country": ", ".join(
                    country.get("name", "")
                    for country in fields.get("country", [])
                ),
                "date": fields.get("date", {}).get("original"),
                "source": source_name,
                "url": fields.get("url"),
            }
        )

    return pd.DataFrame(records)


def main() -> None:
    print("Fetching ReliefWeb reports...")

    payload = fetch_reliefweb_reports(limit=10)

    if payload is None:
        print("ReliefWeb ingestion skipped or failed gracefully.")
        return

    output_path = save_raw_payload(payload)
    df = payload_to_dataframe(payload)

    print(f"Saved raw payload to: {output_path}")
    print(f"Fetched {len(df)} reports.")

    if not df.empty:
        print(df.head().to_string(index=False))


if __name__ == "__main__":
    main()