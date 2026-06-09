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

-- Week 3: Simulated humanitarian coordination data

CREATE TABLE IF NOT EXISTS organizations (
    org_id        TEXT PRIMARY KEY,
    org_name      TEXT NOT NULL,
    org_type      TEXT,
    country       TEXT,
    contact_email TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS zones (
    zone_id              TEXT PRIMARY KEY,
    zone_name            TEXT NOT NULL,
    country              TEXT,
    admin_region         TEXT,
    latitude             DOUBLE PRECISION,
    longitude            DOUBLE PRECISION,
    population_estimate  INTEGER,
    crisis_event_id      TEXT NULL,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resource_inventory (
    inventory_id       TEXT PRIMARY KEY,
    org_id             TEXT REFERENCES organizations(org_id),
    zone_id            TEXT REFERENCES zones(zone_id),
    resource_type      TEXT NOT NULL,
    quantity_available INTEGER NOT NULL,
    unit               TEXT,
    last_updated       TIMESTAMP,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resource_requests (
    request_id         TEXT PRIMARY KEY,
    zone_id            TEXT REFERENCES zones(zone_id),
    resource_type      TEXT NOT NULL,
    quantity_needed    INTEGER NOT NULL,
    urgency_level      TEXT,
    requested_by       TEXT,
    request_timestamp  TIMESTAMP,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
