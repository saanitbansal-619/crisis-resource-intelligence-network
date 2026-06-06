"""
GDACS RSS ingestion script.

Fetches global disaster alerts from the GDACS RSS feed, saves raw XML to
data/raw/, and returns a summary DataFrame for downstream processing.

Run: python -m ingestion.gdacs_ingest
"""

import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

GDACS_RSS_URL = os.getenv(
    "GDACS_RSS_URL",
    "https://www.gdacs.org/xml/rss.xml",
)
RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def fetch_gdacs_rss() -> str:
    """Fetch the GDACS disaster alert RSS feed."""
    response = requests.get(GDACS_RSS_URL, timeout=30)
    response.raise_for_status()
    return response.text


def save_raw_payload(xml_text: str) -> Path:
    """Persist the raw RSS response as timestamped XML."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = RAW_DATA_DIR / f"gdacs_alerts_{timestamp}.xml"
    output_path.write_text(xml_text, encoding="utf-8")
    return output_path


def rss_to_dataframe(xml_text: str) -> pd.DataFrame:
    """Parse GDACS RSS items into a flat DataFrame."""
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return pd.DataFrame()

    records = []
    for item in channel.findall("item"):
        records.append(
            {
                "title": item.findtext("title"),
                "link": item.findtext("link"),
                "pub_date": item.findtext("pubDate"),
                "description": item.findtext("description"),
            }
        )
    return pd.DataFrame(records)


def main() -> None:
    print("Fetching GDACS disaster alerts...")
    xml_text = fetch_gdacs_rss()
    output_path = save_raw_payload(xml_text)
    df = rss_to_dataframe(xml_text)

    print(f"Saved raw payload to: {output_path}")
    print(f"Fetched {len(df)} alerts.")
    if not df.empty:
        print(df.head().to_string(index=False))


if __name__ == "__main__":
    main()
