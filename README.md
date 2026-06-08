# Crisis Resource Intelligence Network

A full-stack data engineering, analytics, and machine learning platform for tracking humanitarian crisis data and identifying resource supply-demand mismatches.

## Problem Statement

Humanitarian crises create urgent, uneven demand for food, water, shelter, medical supplies, and personnel. Public data sources such as ReliefWeb and GDACS publish alerts and situation reports, but turning that information into actionable resource intelligence — knowing where shortages exist and where surplus can be redirected — requires ingestion, normalization, analytics, and accessible tooling. This project builds that pipeline end to end.

## Planned Architecture

```
ReliefWeb API ──┐
                ├──> Ingestion ──> Raw Storage ──> Cleaning ──> PostgreSQL
GDACS RSS    ───┘                                              │
                                                               ├──> Mismatch Analytics
                                                               ├──> FastAPI (REST)
                                                               ├──> Streamlit Dashboard
                                                               ├──> ML Shortage-Risk Prediction (later)
                                                               └──> RAG Crisis Assistant (later)
```

## Tech Stack

| Layer        | Technology                          |
|--------------|-------------------------------------|
| Ingestion    | Python, requests, pandas            |
| Database     | PostgreSQL, SQLAlchemy              |
| Analytics    | SQL, pandas                         |
| Backend API  | FastAPI, uvicorn                    |
| Dashboard    | Streamlit, plotly                   |
| ML (planned) | scikit-learn / similar              |
| RAG (planned)| embeddings + vector store           |
| Local infra  | Docker Compose (PostgreSQL)         |

## Current Status

**Week 1 setup is complete.** Both external data sources are ingesting successfully in a local-only development environment.

**Week 2 in progress:** Raw API data is converted into processed CSVs and loaded into a local PostgreSQL database. ReliefWeb and GDACS data are normalized separately, then upserted into `crisis_reports` and `gdacs_alerts` tables.

### Working features

- ReliefWeb API ingestion with approved appname support (loaded from `.env`)
- GDACS alert ingestion
- Raw data saving to `data/raw/`
- ReliefWeb and GDACS cleaning scripts producing processed CSVs in `data/processed/`
- Local PostgreSQL database via Docker Compose
- Schema and loader scripts for `crisis_reports` and `gdacs_alerts` tables
- Basic pandas inspection of ReliefWeb reports and GDACS alerts
- Local-only development setup (FastAPI and Streamlit starters included)

### Next steps

- Build simulated NGO resource inventory
- Implement supply-demand mismatch scoring
- Expose database tables through FastAPI endpoints

## Data Sources

| Source | Description |
|--------|-------------|
| [ReliefWeb API](https://apidoc.reliefweb.int/) | Humanitarian reports and situation updates |
| [GDACS](https://www.gdacs.org/) | Disaster alerts and crisis event metadata |

## How to Run the Initial Scripts

### 1. Set up the environment

```bash
cd CrisisResourceIntel
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # then set RELIEFWEB_APPNAME to your approved appname
```

Environment setup is documented in [docs/env_setup.md](docs/env_setup.md).

### 2. Run ingestion scripts

```bash
python -m ingestion.reliefweb_ingest
python -m ingestion.gdacs_ingest
```

Raw API responses are saved under `data/raw/`.

> **Note:** ReliefWeb v2 requires a [pre-approved appname](https://apidoc.reliefweb.int/parameters#appname). Set `RELIEFWEB_APPNAME` in `.env` after approval. GDACS works without registration.

### 3. Run cleaning scripts (Week 2)

Normalize the latest raw files into processed CSVs:

```bash
python -m ingestion.clean_reliefweb
python -m ingestion.clean_gdacs
```

Processed outputs are saved under `data/processed/`:
- `reliefweb_reports_clean.csv`
- `gdacs_alerts_clean.csv`

These files standardize dates, flatten nested fields, and prepare crisis metadata for PostgreSQL loading.

## Local PostgreSQL Setup

Start the local database, verify connectivity, and load processed CSVs into PostgreSQL tables.

```bash
docker compose up -d
python -m database.test_connection
python -m database.load_reports
```

`database/load_reports.py` reads `data/processed/reliefweb_reports_clean.csv` and `data/processed/gdacs_alerts_clean.csv`, creates tables from `database/schema.sql` if needed, and upserts rows into:

| Table | Source CSV |
|-------|------------|
| `crisis_reports` | `reliefweb_reports_clean.csv` |
| `gdacs_alerts` | `gdacs_alerts_clean.csv` |

Copy `.env.example` to `.env` and set the `POSTGRES_*` variables (or `DATABASE_URL`) to match `docker-compose.yml`. Rerunning the loader updates existing rows without creating duplicates.

### 4. Start the FastAPI backend

```bash
uvicorn backend.main:app --reload
```

- API root: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### 5. Start the Streamlit dashboard

```bash
streamlit run dashboard/app.py
```

Dashboard opens at http://localhost:8501 by default.

## Project Structure

```
CrisisResourceIntel/
├── ingestion/       # API fetchers, clean_reliefweb.py, clean_gdacs.py
├── database/        # Schema, loaders, seed data
├── analytics/       # Mismatch engine and SQL queries
├── backend/         # FastAPI application
├── dashboard/       # Streamlit UI
├── ml/              # Shortage-risk prediction (future)
├── rag/             # Crisis assistant (future)
├── data/            # Raw, processed, and sample data
├── docs/            # Architecture and dev notes
└── tests/           # Test suite (future)
```

## License

TBD
