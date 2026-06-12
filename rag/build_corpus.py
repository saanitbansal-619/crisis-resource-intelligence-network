"""
Build a local JSON corpus from ReliefWeb and GDACS records in PostgreSQL.

Run: python -m rag.build_corpus
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
RAG_DIR = PROJECT_ROOT / "data" / "rag"
CORPUS_PATH = RAG_DIR / "corpus.json"

load_dotenv(dotenv_path=ENV_PATH, override=True, encoding="utf-8-sig")


def _parse_database_url_manual(env_path: Path) -> str | None:
    if not env_path.exists():
        return None
    with env_path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped.startswith("DATABASE_URL="):
                return stripped.split("=", 1)[1].strip()
    return None


def get_database_url() -> str:
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

    print("DATABASE_URL not found. Create a .env file in the project root using .env.example.")
    print(f"Expected .env path: {ENV_PATH}")
    sys.exit(1)


def _clean(value) -> str:
    if value is None:
        return ""
    text_value = str(value).strip()
    if text_value.lower() in {"nan", "none", "null"}:
        return ""
    return text_value


def _combine_text(parts: list[str]) -> str:
    seen = set()
    combined: list[str] = []
    for part in parts:
        cleaned = _clean(part)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        combined.append(cleaned)
    return "\n\n".join(combined)


def _row_value(row, key: str, default: str = "") -> str:
    mapping = row._mapping if hasattr(row, "_mapping") else row
    return _clean(mapping.get(key, default))


def build_reliefweb_document(row) -> dict | None:
    source_id = _row_value(row, "reliefweb_id")
    if not source_id:
        return None

    country = _row_value(row, "primary_country") or _row_value(row, "countries")
    published_at = _row_value(row, "date_parsed") or _row_value(row, "date_original")
    event_type = _row_value(row, "disaster_types")
    title = _row_value(row, "title")
    url = _row_value(row, "url")

    text_body = _combine_text([
        title,
        f"Country: {country}" if country else "",
        f"Disaster types: {event_type}" if event_type else "",
        f"Themes: {_row_value(row, 'themes')}" if _row_value(row, "themes") else "",
        f"Source: {_row_value(row, 'source_name')}" if _row_value(row, "source_name") else "",
        _row_value(row, "body_text"),
    ])

    if not text_body:
        return None

    return {
        "doc_id": f"reliefweb_{source_id}",
        "source_type": "reliefweb",
        "source_id": source_id,
        "title": title,
        "country": country,
        "event_type": event_type,
        "published_at": published_at,
        "url": url,
        "text": text_body,
    }


def build_gdacs_document(row) -> dict | None:
    source_id = _row_value(row, "alert_id")
    if not source_id:
        return None

    title = _row_value(row, "title")
    country = _row_value(row, "country")
    event_type = _row_value(row, "event_type")
    published_at = _row_value(row, "pub_date_parsed") or _row_value(row, "pub_date")
    url = _row_value(row, "link")
    severity = _row_value(row, "severity_color")

    text_body = _combine_text([
        title,
        f"Event type: {event_type}" if event_type else "",
        f"Country: {country}" if country else "",
        f"Severity: {severity}" if severity else "",
        _row_value(row, "description"),
    ])

    if not text_body:
        return None

    return {
        "doc_id": f"gdacs_{source_id}",
        "source_type": "gdacs",
        "source_id": source_id,
        "title": title,
        "country": country,
        "event_type": event_type,
        "published_at": published_at,
        "url": url,
        "text": text_body,
    }


def build_corpus() -> list[dict]:
    engine = create_engine(get_database_url())
    documents: list[dict] = []

    with engine.connect() as conn:
        reliefweb_rows = conn.execute(
            text(
                """
                SELECT
                    reliefweb_id,
                    title,
                    countries,
                    primary_country,
                    date_original,
                    date_parsed,
                    source_name,
                    source_type,
                    disaster_types,
                    themes,
                    language,
                    url,
                    body_text
                FROM crisis_reports
                ORDER BY date_parsed DESC NULLS LAST, reliefweb_id
                """
            )
        )
        for row in reliefweb_rows:
            doc = build_reliefweb_document(row)
            if doc:
                documents.append(doc)

        gdacs_rows = conn.execute(
            text(
                """
                SELECT
                    alert_id,
                    title,
                    event_type,
                    severity_color,
                    country,
                    pub_date,
                    pub_date_parsed,
                    description,
                    link
                FROM gdacs_alerts
                ORDER BY pub_date_parsed DESC NULLS LAST, alert_id
                """
            )
        )
        for row in gdacs_rows:
            doc = build_gdacs_document(row)
            if doc:
                documents.append(doc)

    return documents


def save_corpus(documents: list[dict]) -> Path:
    RAG_DIR.mkdir(parents=True, exist_ok=True)
    CORPUS_PATH.write_text(json.dumps(documents, indent=2, default=str), encoding="utf-8")
    return CORPUS_PATH


def main() -> None:
    documents = build_corpus()
    output_path = save_corpus(documents)

    reliefweb_count = sum(1 for doc in documents if doc["source_type"] == "reliefweb")
    gdacs_count = sum(1 for doc in documents if doc["source_type"] == "gdacs")

    print("Corpus build complete.")
    print(f"ReliefWeb documents added: {reliefweb_count}")
    print(f"GDACS documents added: {gdacs_count}")
    print(f"Total corpus documents saved: {len(documents)}")
    print(f"Output path: {output_path}")


if __name__ == "__main__":
    main()
