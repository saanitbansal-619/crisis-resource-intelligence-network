-- Crisis Resource Intelligence Network — PostgreSQL schema (Week 2)
-- Idempotent: safe to rerun via load_reports.py

CREATE TABLE IF NOT EXISTS crisis_reports (
    reliefweb_id    TEXT PRIMARY KEY,
    title           TEXT,
    countries       TEXT,
    primary_country TEXT,
    date_original   TEXT,
    date_parsed     TIMESTAMP NULL,
    source_name     TEXT,
    source_type     TEXT,
    disaster_types  TEXT,
    themes          TEXT,
    language        TEXT,
    url             TEXT,
    body_text       TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gdacs_alerts (
    alert_id        TEXT PRIMARY KEY,
    title           TEXT,
    event_type      TEXT,
    severity_color  TEXT,
    country         TEXT,
    pub_date        TEXT,
    pub_date_parsed TIMESTAMP NULL,
    description     TEXT,
    link            TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
