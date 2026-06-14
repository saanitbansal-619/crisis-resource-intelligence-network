# Crisis Resource Intelligence Network

A full-stack data engineering, analytics, and machine learning platform for tracking humanitarian crisis data and identifying resource supply-demand mismatches.

## Problem Statement

Humanitarian crises create urgent, uneven demand for food, water, shelter, medical supplies, and personnel. Public data sources such as ReliefWeb and GDACS publish alerts and situation reports, but turning that information into actionable resource intelligence — knowing where shortages exist and where surplus can be redirected — requires ingestion, normalization, analytics, and accessible tooling. This project builds that pipeline end to end.

## Architecture

```
ReliefWeb API ──┐
                ├──> Ingestion ──> Raw Storage ──> Cleaning ──> PostgreSQL
GDACS RSS    ───┘                                              │
                                                               ├──> Mismatch Analytics
                                                               ├──> FastAPI (REST)
                                                               ├──> Streamlit Dashboard
                                                               ├──> RAG corpus + pgvector retrieval
                                                               └──> Local LLM briefing (Ollama)
```

### RAG pipeline

The project includes a retrieval-augmented briefing layer:

```
ReliefWeb/GDACS crisis records
  → corpus building
  → document chunking
  → Ollama nomic-embed-text embeddings
  → PostgreSQL pgvector vector storage
  → hybrid semantic + keyword retrieval
  → metadata boosting by country/event/source
  → fallback labeling
  → local LLM briefing generation with Ollama llama3.2
```

## Tech Stack

| Layer        | Technology                                      |
|--------------|-------------------------------------------------|
| Ingestion    | Python, requests, pandas                        |
| Database     | PostgreSQL, pgvector, SQLAlchemy                |
| Analytics    | SQL, pandas, scikit-learn (TF-IDF keyword scoring) |
| Backend API  | FastAPI, uvicorn                                |
| Dashboard    | Streamlit, Plotly                               |
| Embeddings   | Ollama `nomic-embed-text` (768-dim)             |
| Generation   | Ollama `llama3.2` (local LLM)                   |
| Local infra  | Docker Compose (PostgreSQL + pgvector)          |

## Current Status

**Week 1 setup is complete.** Both external data sources are ingesting successfully in a local-only development environment.

**Week 2 complete:** Raw API data is converted into processed CSVs and loaded into a local PostgreSQL database. ReliefWeb and GDACS data are normalized separately, then upserted into `crisis_reports` and `gdacs_alerts` tables.

**Week 3 complete:** Simulated humanitarian coordination data and supply-demand mismatch analytics are in PostgreSQL.

**Week 4 complete:** FastAPI backend exposes crisis data, resources, mismatches, and summary reports via REST.

**Week 5 complete:** Streamlit humanitarian coordination dashboard consumes the FastAPI backend with an NGO-oriented visual style for stakeholder presentation.

**Week 6 Part 1 complete:** Zone briefing endpoint and map-based Zone Operational Briefs on the Operational Map page generate template-based coordination briefs from PostgreSQL-backed data.

**Week 6 Part 2 complete:** RAG retrieval over ReliefWeb/GDACS records with pgvector semantic search, hybrid keyword scoring, metadata boosting, fallback labeling, and optional local LLM-assisted operational briefings via Ollama.

**Final system status (portfolio prototype):**

- Full dashboard workflow is complete
- Hybrid RAG retrieval is complete
- Local LLM briefing generation is complete
- Dashboard error handling was added for demo reliability
- Screenshots and demo recording are the remaining presentation tasks

This is not production-ready. Operational inventory and request data are simulated, AI briefings are drafts, and public crisis context depends on available ReliefWeb/GDACS records.

### Working features

- ReliefWeb API ingestion with approved appname support (loaded from `.env`)
- GDACS alert ingestion
- Raw data saving to `data/raw/`
- ReliefWeb and GDACS cleaning scripts producing processed CSVs in `data/processed/`
- Local PostgreSQL database via Docker Compose with pgvector (host port 5433)
- Schema and loader scripts for `crisis_reports` and `gdacs_alerts` tables
- Simulated organizations, zones, resource inventory, and resource requests
- Basic pandas inspection of ReliefWeb reports and GDACS alerts
- Local-only development setup (FastAPI and Streamlit starters included)
- RAG corpus building, chunking, embedding, and hybrid retrieval
- Zone-level retrieved crisis context and optional AI-assisted briefing endpoints
- Operational Map with template briefs, retrieved context, and on-demand AI draft generation
- Graceful dashboard error handling when FastAPI, PostgreSQL, or Ollama is unavailable
- Demo health check script (`python -m scripts.health_check`)

### Next steps

- Add ML shortage-risk prediction
- Scheduled ingestion and cloud deployment
- Refresh dashboard screenshots and record a demo walkthrough

## Demo Health Check

Before running the dashboard demo, verify local services:

```bash
python -m scripts.health_check
```

Expected output when all services are available:

```
[OK] Database connection
[OK] FastAPI backend
[OK] RAG context endpoint
[OK] AI briefing endpoint
```

If Ollama is not running, the AI check may show a warning instead:

```
[WARN] AI briefing endpoint: Ollama may not be running
```

| Check | Verifies |
|-------|----------|
| Database connection | PostgreSQL is reachable using `DATABASE_URL` from `.env` |
| FastAPI backend | API is running at `http://127.0.0.1:8001/` |
| RAG context endpoint | Hybrid RAG retrieval works for `ZONE001` via `/reports/rag-zone-context/ZONE001` |
| AI briefing endpoint | Ollama-powered draft briefing works via `/reports/ai-zone-briefing/ZONE001` |

The AI briefing endpoint depends on **Ollama running locally** with **`llama3.2` available**. The dashboard still works without it; template briefs and retrieved context remain available when only PostgreSQL and FastAPI are running.

Start services before the health check:

```bash
docker compose up -d
uvicorn backend.main:app --reload --port 8001
ollama serve   # if testing AI briefing
```

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

Docker uses the **pgvector/pgvector** image and maps **host port 5433** to **container port 5432** so this project does not conflict with other PostgreSQL services on port 5432.

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

Copy `.env.example` to `.env` and set `DATABASE_URL` and `POSTGRES_PORT` to use port **5433** (matching `docker-compose.yml`). Rerunning the loader updates existing rows without creating duplicates.

## Week 3: Simulated Resource Data

Real NGO inventory and medical supply data is not publicly available for privacy, security, and operational reasons. Week 3 adds **simulated** humanitarian coordination data so the project can prototype supply-demand mismatch analysis using realistic schema and workflows.

New tables:

| Table | Description |
|-------|-------------|
| `organizations` | NGOs, UN agencies, and government responders |
| `zones` | Geographic crisis response areas linked to events |
| `resource_inventory` | Supply available by organization and zone |
| `resource_requests` | Demand requests by zone and resource type |

Generate and load simulated data:

```bash
python -m database.generate_sample_resources
python -m database.load_resources
```

Sample CSVs are saved to `data/sample/` and loaded into PostgreSQL with upsert logic. Some zones are intentionally modeled with shortages; others have surplus inventory.

### Supply-demand mismatch engine

`mismatch_scores` is the first analytics table derived from resource inventory and request data. It compares supply vs. demand by zone and resource type, applies urgency weighting, and assigns status labels (surplus, stable, moderate/severe/critical shortage).

```bash
python -m analytics.mismatch_engine
```

SQL query templates for shortages, surpluses, and summaries live in `analytics/queries/`.

## Week 4: FastAPI Backend

The FastAPI backend exposes PostgreSQL data and mismatch analytics through REST endpoints. It separates the database/analytics layer from future dashboard and AI features.

Start the API (port 8001 for dashboard compatibility):

```bash
uvicorn backend.main:app --reload --port 8001
```

- Interactive docs: http://127.0.0.1:8001/docs
- Health check: http://127.0.0.1:8001/health
- API root: http://127.0.0.1:8001/

Endpoint groups:

| Prefix | Description |
|--------|-------------|
| `/crises` | ReliefWeb reports and GDACS alerts |
| `/resources` | Zones, organizations, inventory, requests |
| `/mismatches` | Shortage/surplus analytics with filters |
| `/reports` | KPI overview, zone briefings, RAG context, AI briefings |

Zone briefing (consolidated data for one zone):

```
GET /reports/zone-briefing/{zone_id}
GET /reports/rag-zone-context/{zone_id}
GET /reports/ai-zone-briefing/{zone_id}
```

Examples:
- http://127.0.0.1:8001/reports/zone-briefing/ZONE001
- http://127.0.0.1:8001/reports/rag-zone-context/ZONE001
- http://127.0.0.1:8001/reports/ai-zone-briefing/ZONE001

## Week 5: Streamlit Operations Dashboard

The Streamlit dashboard consumes the FastAPI backend and presents crisis resource intelligence in a professional humanitarian operations style. It includes situation overview KPIs, priority needs, available surplus, resource balance, and an operational map.

Before a demo, run `python -m scripts.health_check` to confirm PostgreSQL, FastAPI, RAG, and (optionally) Ollama are available.

Run in two terminals:

Terminal 1 — API:
```bash
uvicorn backend.main:app --reload --port 8001
```

Terminal 2 — Dashboard:
```bash
streamlit run dashboard/app.py
```

Dashboard URL: http://localhost:8501

The dashboard connects to the local API at `http://127.0.0.1:8001` internally and uses a humanitarian operations visual style—light background, white cards, muted severity colors, and field-coordination language—for NGO, academic, and non-technical stakeholder presentations. The Situation Overview tab explains data sources, workflow, and how priority scores are calculated.

## Week 6 Part 1: Map-Based Zone Operational Briefs

The **Operational Map** supports selected-zone briefing preview. Users select a zone via map marker click or the zone selector, review a compact **Selected Zone** panel, then choose to view the formatted **Zone Operational Brief** in-app, download a PDF, or open copy-ready text. The full brief is not shown until the user clicks **View Operational Brief**.

Template-based operational briefs remain the **stable default**. They are deterministic and grounded in PostgreSQL data—no external LLM required. PDF export is optional and uses ReportLab (`pip install reportlab`). If ReportLab is not installed, the dashboard shows a clear warning instead of crashing.

**Operational Map features:**

- Zone selection via map marker or dropdown
- Template operational briefing (default)
- Retrieved crisis context from ReliefWeb/GDACS records
- Optional **Generate AI-Assisted Brief** button (on-demand, local Ollama)
- PDF download and copy brief actions
- Data transparency note (public vs simulated sources)

## Week 6 Part 2: RAG and Local LLM Briefings

### Retrieval-augmented context

After viewing a template brief, the dashboard can fetch **Retrieved Crisis Context** for the selected zone. Retrieval uses hybrid semantic + keyword search over ReliefWeb/GDACS chunks stored in PostgreSQL with pgvector. Results are boosted by country, event type, and source metadata. If too few country-specific records match, fallback results are included and labeled `is_fallback: true`.

**Setup (one-time, after PostgreSQL is running and Ollama is available):**

```bash
# Start Ollama and pull models
ollama pull nomic-embed-text
ollama pull llama3.2

# Build corpus, chunks, and vector tables
python -m rag.build_corpus
python -m rag.chunk_documents
python -m database.create_rag_tables
python -m rag.embed_chunks
```

**Backend endpoints:**

```
GET /reports/rag-zone-context/{zone_id}
GET /reports/ai-zone-briefing/{zone_id}
```

### Local LLM generation

AI-assisted operational briefings are generated **locally** using Ollama `llama3.2`. The prompt is grounded in structured zone metrics and retrieved context:

- The selected zone's related disaster alert is treated as the **primary event**
- Retrieved sources are **supporting context only**
- The model is instructed **not to invent facts**
- The dashboard labels the output as an **AI-assisted draft requiring review**
- Template-based operational briefs remain the stable default

AI briefings are optional and on-demand. They do not replace the template brief, PDF export, or copy actions.

## Limitations

This is a **portfolio prototype**, not a production deployment:

- Operational inventory and resource request data are **simulated prototype data**, not real NGO supply systems
- Public humanitarian records are limited to what ReliefWeb and GDACS provide
- AI-generated briefings are **drafts** and should be reviewed before any operational use
- The system does not make final operational decisions and should not be presented as production-ready

## Dashboard Screenshots

![Situation Overview](docs/screenshots/situation_overview.png)
![Priority Needs](docs/screenshots/priority_needs.png)
![Available Surplus](docs/screenshots/available_surplus.png)
![Resource Balance](docs/screenshots/resource_balance.png)
![Operational Map](docs/screenshots/operational_map.png)
![Zone Operational Brief](docs/screenshots/zone_operational_brief.png)

## Project Structure

```
CrisisResourceIntel/
├── ingestion/       # API fetchers, clean_reliefweb.py, clean_gdacs.py
├── database/        # Schema, loaders, sample resource generator
├── analytics/       # Mismatch engine and SQL queries
├── backend/         # FastAPI application
├── dashboard/       # Streamlit UI
├── scripts/         # Demo health check and utilities
├── ml/              # Shortage-risk prediction (future)
├── rag/             # Corpus, embeddings, hybrid retrieval, LLM briefing
├── data/            # Raw, processed, and sample data
├── docs/            # Architecture and dev notes
└── tests/           # Test suite (future)
```

## License

TBD
