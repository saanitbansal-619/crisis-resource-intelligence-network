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

## Current Status: Week 1 Setup

- Project skeleton with all module directories and placeholder files
- Runnable ReliefWeb and GDACS ingestion scripts
- FastAPI starter with health-check endpoints
- Streamlit starter dashboard
- PostgreSQL docker-compose configuration (not yet connected to app code)
- ML and RAG modules stubbed for future sprints

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
cp .env.example .env
```

### 2. Start PostgreSQL (optional for Week 1)

```bash
docker compose up -d
```

### 3. Run ingestion scripts

```bash
python -m ingestion.reliefweb_ingest
python -m ingestion.gdacs_ingest
```

Raw API responses are saved under `data/raw/`.

> **Note:** ReliefWeb v2 requires a [pre-approved appname](https://apidoc.reliefweb.int/parameters#appname). Set `RELIEFWEB_APPNAME` in `.env` after approval. GDACS works without registration.

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
