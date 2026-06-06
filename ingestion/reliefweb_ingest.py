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

load_dotenv()

RELIEFWEB_API_URL = os.getenv(
    "RELIEFWEB_API_URL",
    "https://api.reliefweb.int/v2/reports",
)
RELIEFWEB_APPNAME = os.getenv("RELIEFWEB_APPNAME", "crisis-resource-intel")
RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def fetch_reliefweb_reports(limit: int = 10) -> dict:
    """Fetch recent reports from the ReliefWeb API (v2)."""
    params = {
        "appname": RELIEFWEB_APPNAME,
        "profile": "full",
        "limit": limit,
        "sort[]": "date:desc",
    }
    response = requests.get(RELIEFWEB_API_URL, params=params, timeout=30)
    if response.status_code == 403:
        raise PermissionError(
            "ReliefWeb requires a pre-approved appname. "
            "Request one at https://apidoc.reliefweb.int/parameters#appname "
            "and set RELIEFWEB_APPNAME in your .env file."
        )
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
        records.append(
            {
                "id": item.get("id"),
                "title": fields.get("title"),
                "country": ", ".join(
                    country.get("name", "")
                    for country in fields.get("country", [])
                ),
                "date": fields.get("date", {}).get("original"),
                "source": fields.get("source", {}).get("name"),
                "url": fields.get("url"),
            }
        )
    return pd.DataFrame(records)


def main() -> None:
    print("Fetching ReliefWeb reports...")
    payload = fetch_reliefweb_reports(limit=10)
    output_path = save_raw_payload(payload)
    df = payload_to_dataframe(payload)

    print(f"Saved raw payload to: {output_path}")
    print(f"Fetched {len(df)} reports.")
    if not df.empty:
        print(df.head().to_string(index=False))


if __name__ == "__main__":
    main()
