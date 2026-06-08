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

### Working features

- ReliefWeb API ingestion with approved appname support (loaded from `.env`)
- GDACS alert ingestion
- Raw data saving to `data/raw/`
- Basic pandas inspection of ReliefWeb reports and GDACS alerts
- Local-only development setup (FastAPI and Streamlit starters included)

### Next steps

- Clean and normalize ReliefWeb/GDACS data
- Design PostgreSQL schema
- Load processed crisis data into PostgreSQL
- Build simulated NGO resource inventory
- Implement supply-demand mismatch scoring

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

### 2. Run ingestion scripts

```bash
python -m ingestion.reliefweb_ingest
python -m ingestion.gdacs_ingest
```

Raw API responses are saved under `data/raw/`.

> **Note:** ReliefWeb v2 requires a [pre-approved appname](https://apidoc.reliefweb.int/parameters#appname). Set `RELIEFWEB_APPNAME` in `.env` after approval. GDACS works without registration.

### 3. Start the FastAPI backend

```bash
uvicorn backend.main:app --reload
```

- API root: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### 4. Start the Streamlit dashboard

```bash
streamlit run dashboard/app.py
```

Dashboard opens at http://localhost:8501 by default.

## Project Structure

```
CrisisResourceIntel/
├── ingestion/       # API data fetchers and cleaning
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
