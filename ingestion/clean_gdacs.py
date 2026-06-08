"""
GDACS alert data cleaning and normalization.

Reads the most recent raw GDACS file from data/raw/ (XML, JSON, or CSV),
normalizes alert metadata into a flat table, and writes a processed CSV.

Run: python -m ingestion.clean_gdacs
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_FILE = PROCESSED_DATA_DIR / "gdacs_alerts_clean.csv"

GDACS_NS = {"gdacs": "http://www.gdacs.org"}

EVENT_TYPE_MAP = {
    "EQ": "earthquake",
    "FL": "flood",
    "TC": "tropical cyclone",
    "VO": "volcano",
    "DR": "drought",
}

OUTPUT_COLUMNS = [
    "alert_id",
    "title",
    "event_type",
    "severity_color",
    "country",
    "pub_date",
    "pub_date_parsed",
    "description",
    "link",
]


def find_latest_raw_file() -> Path | None:
    """Return the most recent GDACS raw file in data/raw/."""
    patterns = ["gdacs_alerts_*.xml", "gdacs_alerts_*.json", "gdacs_alerts_*.csv"]
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(RAW_DATA_DIR.glob(pattern))

    if not candidates:
        return None

    return max(candidates, key=lambda path: path.stat().st_mtime)


def _event_code_from_link(link: str | None) -> str | None:
    """Extract event type code from a GDACS report URL."""
    if not link:
        return None
    query = parse_qs(urlparse(link).query)
    event_type = query.get("eventtype", [None])[0]
    return event_type.upper() if event_type else None


def _event_code_from_title(title: str | None) -> str | None:
    """Infer event type code from keywords in the alert title."""
    if not title:
        return None
    title_lower = title.lower()
    keyword_map = {
        "earthquake": "EQ",
        "flood": "FL",
        "tropical cyclone": "TC",
        "cyclone": "TC",
        "volcano": "VO",
        "drought": "DR",
        "forest fire": "WF",
    }
    for keyword, code in keyword_map.items():
        if keyword in title_lower:
            return code
    return None


def infer_event_type(
    title: str | None,
    link: str | None,
    xml_event_type: str | None = None,
) -> str:
    """Map GDACS event codes to readable event type labels."""
    code = (xml_event_type or "").upper() or _event_code_from_link(link) or _event_code_from_title(title)
    if not code:
        return ""
    return EVENT_TYPE_MAP.get(code, code.lower())


def infer_severity_color(title: str | None) -> str:
    """Infer alert severity from title prefix (Green, Orange, Red)."""
    if not title:
        return ""
    for color in ("Green", "Orange", "Red"):
        if title.startswith(color):
            return color
    return ""


def infer_country(
    title: str | None,
    description: str | None,
    xml_country: str | None = None,
) -> str:
    """Infer country from GDACS fields or title/description text."""
    if xml_country:
        return xml_country.strip()

    if title:
        match = re.search(r" alert in (.+)$", title, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()

        match = re.search(r" in ([A-Za-z\u00C0-\u024F\u1E00-\u1EFF' -]+?) \d", title)
        if match:
            return match.group(1).strip()

    if description:
        match = re.search(
            r"(?:started|occurred) in ([A-Za-z\u00C0-\u024F\u1E00-\u1EFF' -]+?)(?:,| potentially|\.)",
            description,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()

    return ""


def _parse_xml_items(xml_text: str) -> list[dict]:
    """Parse GDACS RSS XML into normalized record dicts."""
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return []

    records = []
    for item in channel.findall("item"):
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        pub_date = item.findtext("pubDate") or ""
        description = item.findtext("description") or ""

        xml_event_type = item.findtext("gdacs:eventtype", namespaces=GDACS_NS) or ""
        xml_country = item.findtext("gdacs:country", namespaces=GDACS_NS) or ""
        alert_id = item.findtext("gdacs:eventid", namespaces=GDACS_NS) or ""

        if not alert_id and link:
            query = parse_qs(urlparse(link).query)
            alert_id = query.get("eventid", [""])[0]

        records.append(
            {
                "alert_id": alert_id,
                "title": title,
                "event_type": infer_event_type(title, link, xml_event_type),
                "severity_color": infer_severity_color(title)
                or (item.findtext("gdacs:alertlevel", namespaces=GDACS_NS) or ""),
                "country": infer_country(title, description, xml_country),
                "pub_date": pub_date,
                "pub_date_parsed": pd.to_datetime(pub_date, errors="coerce", utc=True),
                "description": description,
                "link": link,
            }
        )

    return records


def load_raw_file(raw_path: Path) -> list[dict]:
    """Load GDACS records from XML, JSON, or CSV raw files."""
    suffix = raw_path.suffix.lower()

    if suffix == ".xml":
        return _parse_xml_items(raw_path.read_text(encoding="utf-8"))

    if suffix == ".json":
        df = pd.read_json(raw_path)
        return _normalize_dataframe_records(df)

    if suffix == ".csv":
        df = pd.read_csv(raw_path)
        return _normalize_dataframe_records(df)

    raise ValueError(f"Unsupported GDACS raw file format: {suffix}")


def _normalize_dataframe_records(df: pd.DataFrame) -> list[dict]:
    """Normalize tabular GDACS records into the standard output schema."""
    records = []
    for row in df.to_dict(orient="records"):
        title = str(row.get("title", "") or "")
        link = str(row.get("link", "") or "")
        pub_date = str(row.get("pub_date", "") or row.get("pubDate", "") or "")
        description = str(row.get("description", "") or "")

        records.append(
            {
                "alert_id": str(row.get("alert_id", "") or row.get("eventid", "") or ""),
                "title": title,
                "event_type": infer_event_type(
                    title,
                    link,
                    str(row.get("event_type", "") or row.get("eventtype", "") or ""),
                ),
                "severity_color": infer_severity_color(title)
                or str(row.get("severity_color", "") or row.get("alertlevel", "") or ""),
                "country": infer_country(
                    title,
                    description,
                    str(row.get("country", "") or ""),
                ),
                "pub_date": pub_date,
                "pub_date_parsed": pd.to_datetime(pub_date, errors="coerce", utc=True),
                "description": description,
                "link": link,
            }
        )
    return records


def load_and_clean(raw_path: Path) -> pd.DataFrame:
    """Load a raw GDACS file and return a normalized DataFrame."""
    records = load_raw_file(raw_path)
    return pd.DataFrame(records, columns=OUTPUT_COLUMNS)


def main() -> None:
    raw_path = find_latest_raw_file()
    if raw_path is None:
        print("No GDACS raw file found in data/raw/.")
        print("Run: python -m ingestion.gdacs_ingest")
        return

    print(f"Loaded raw file: {raw_path}")
    df = load_and_clean(raw_path)

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"Cleaned {len(df)} records.")
    print(f"Saved processed CSV to: {OUTPUT_FILE}")

    if not df.empty:
        preview = df.head().copy()
        preview["description"] = preview["description"].str.slice(0, 80) + "..."
        print(preview.to_string(index=False))


if __name__ == "__main__":
    main()
