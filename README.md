# Crisis Resource Intelligence Network

[![Tests](https://github.com/saanitbansal-619/crisis-resource-intelligence-network/actions/workflows/tests.yml/badge.svg)](https://github.com/saanitbansal-619/crisis-resource-intelligence-network/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.11-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## Overview

Humanitarian crises create uneven demand for food, water, shelter, medical supplies, and personnel. Public sources such as ReliefWeb and GDACS publish alerts and situation reports, but turning that information into actionable resource intelligence requires ingestion, normalization, analytics, and accessible decision-support tooling.

Crisis Resource Intelligence Network is an **optimization-driven humanitarian intelligence platform** that integrates ReliefWeb/GDACS crisis-data ingestion, PostgreSQL-backed analytics, FastAPI endpoints, **OR-Tools transport optimization**, **XGBoost shortage-risk forecasting**, and an interactive Streamlit operations dashboard.

It scores supply-demand mismatches from simulated NGO resource data, recommends how surplus could be transferred to shortages under cost and capacity constraints, and forecasts which shortages are likely to escalate over the next 48–72 hours. **AI-assisted briefing support and retrieval-based crisis context (RAG/Ollama) are included as supporting analyst workflows**, not the main headline.

## Portfolio Note

This is a **portfolio prototype**, not a production emergency response system.

- **Public crisis context** comes from ReliefWeb and GDACS.
- **Operational inventory and resource request data are simulated** because real NGO supply data is generally not public.
- Transfer recommendations and AI briefings are decision-support outputs that require human review before any operational use.

## Portfolio Highlights

- Built and deployed an optimization-driven humanitarian intelligence platform integrating ReliefWeb/GDACS ingestion, PostgreSQL, FastAPI, OR-Tools transport optimization, and XGBoost shortage-risk forecasting through an interactive Streamlit dashboard.
- Implemented supply-demand mismatch scoring and optimized surplus-to-shortage transfer recommendations, generating 10 optimized routes and 9,760 simulated units moved while minimizing 19.54M relative transport-cost units.
- Added an ML-based 48–72 hour shortage-risk forecast using proxy operational labels derived from shortage gaps, fulfillment ratios, urgency scores, and mismatch severity.

## Live Demo

- **Dashboard:** [https://crisis-resource-dashboard.onrender.com](https://crisis-resource-dashboard.onrender.com)
- **API Docs:** [https://crisis-resource-api.onrender.com/docs](https://crisis-resource-api.onrender.com/docs)

> **Note:** The deployed demo may take 30–60 seconds to wake up on first load because it is hosted on a free Render instance.

**Hosted deployment note:**

- The deployed dashboard uses a live Render FastAPI backend and Render PostgreSQL database.
- Core dashboard features are available online: KPI overview, situation report, priority needs, surplus, resource balance, operational map, zone briefings, transfer recommendations, and retrieval-based crisis context.
- Semantic RAG retrieval and AI-assisted briefings use local Ollama in full local demo mode.
- In hosted Render mode, when Ollama is unavailable, retrieved crisis context falls back to keyword-based ReliefWeb/GDACS retrieval.
- AI-assisted briefings are shown as local-demo-only when Ollama is unavailable.

## Key Features

- ReliefWeb API and GDACS RSS crisis-data ingestion
- PostgreSQL-backed crisis, resource, inventory, request, and mismatch records (with pgvector)
- Supply-demand mismatch scoring for shortage and surplus detection
- OR-Tools optimized surplus-to-shortage transfer recommendations
- XGBoost shortage-risk forecasting for 48–72 hour escalation risk
- Streamlit dashboard with KPI summaries, maps, reports, transfer plans, and forecast tables
- Retrieval-based crisis context and local Ollama-assisted briefing drafts (supporting analyst workflow)
- Demo health check script

## Tech Stack

| Layer        | Technology                                              |
|--------------|---------------------------------------------------------|
| Ingestion    | Python, requests, pandas                                |
| Database     | PostgreSQL, pgvector, SQLAlchemy                        |
| Hosted DB    | Render PostgreSQL                                       |
| Local DB     | Docker Compose (PostgreSQL + pgvector)                  |
| Analytics    | SQL, pandas, scikit-learn (TF-IDF keyword scoring)      |
| Optimization | Google OR-Tools (minimum-cost transfer planning)         |
| ML forecasting | XGBoost (RandomForest fallback), scikit-learn, joblib  |
| Backend API  | FastAPI, uvicorn (Render Web Service when hosted)       |
| Dashboard    | Streamlit, Plotly (Render Web Service when hosted)        |
| Embeddings   | Ollama `nomic-embed-text` (768-dim, local demo mode)    |
| Generation   | Ollama `llama3.2` (local LLM, local demo mode)            |

## Architecture

```mermaid
flowchart LR
    RW[ReliefWeb API] --> ING[Ingestion / ETL Pipeline]
    GD[GDACS RSS Feeds] --> ING

    ING --> PG[(PostgreSQL + pgvector)]

    PG --> MISMATCH[Mismatch Scoring Engine]
    PG --> FORECAST[XGBoost Shortage-Risk Forecasting]
    PG --> RETRIEVAL[Retrieval-Based Crisis Context]
    PG --> API[FastAPI Backend]

    MISMATCH --> OPT[OR-Tools Transport Optimization]
    OPT --> API
    FORECAST --> API
    RETRIEVAL --> API

    OLLAMA[Local Ollama<br/>Optional AI Briefings] -. local demo only .-> RETRIEVAL
    OLLAMA -. local demo only .-> API

    API --> DASH[Streamlit Dashboard]

    DASH --> KPIS[KPI Overview]
    DASH --> MAPS[Operational Map]
    DASH --> REPORTS[Situation Reports & Zone Briefings]
    DASH --> TRANSFERS[Optimized Transfer Plans]
    DASH --> RISKS[Shortage-Risk Forecasts]
```

This diagram shows the end-to-end system flow from public crisis-data ingestion through PostgreSQL-backed analytics, mismatch scoring, OR-Tools transport optimization, XGBoost shortage-risk forecasting, retrieval, FastAPI endpoints, and the Streamlit operations dashboard. Local Ollama support is optional and used for local semantic retrieval and AI-assisted briefing drafts.

The diagram source lives in [`docs/architecture/architecture.mmd`](docs/architecture/architecture.mmd). To regenerate static image assets with the [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli):

```bash
npx @mermaid-js/mermaid-cli -i docs/architecture/architecture.mmd -o docs/architecture/architecture.svg
npx @mermaid-js/mermaid-cli -i docs/architecture/architecture.mmd -o docs/architecture/architecture.png
```

End-to-end pipeline:

```
ReliefWeb/GDACS ingestion
  → PostgreSQL storage
  → mismatch scoring
  → OR-Tools transport optimization
  → XGBoost shortage-risk forecasting
  → hybrid RAG retrieval with pgvector (supporting)
  → optional local Ollama AI briefing (supporting)
  → dashboard KPIs, maps, transfer plans, and risk forecasts
```

RAG pipeline:

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

## System Statistics

- 2 live humanitarian data sources integrated: ReliefWeb API and GDACS RSS feeds
- 10 crisis zones modeled in the demo database
- 7 organizations represented across inventory and request records
- 24 inventory records and 21 request records analyzed
- 90 GDACS alerts ingested
- 10 ReliefWeb crisis reports processed
- 24 resource mismatch records generated
- 10 optimized transfer recommendations generated
- 9,760 total simulated units moved in the optimized transfer plan
- 19.54M relative simulated transport-cost units minimized by the OR-Tools optimizer
- 24 zone/resource shortage-risk forecasts generated by the ML layer
- 8 zone/resource combinations forecast at high or critical 48-hour shortage risk

Statistics reflect the deployed portfolio/demo dataset and may vary when the ingestion pipeline or forecasting workflow is rerun.

## Dashboard Screenshots

1. **Situation Overview — Operational Snapshot** — KPI cards for zones, shortages, surplus, and tracked gaps.

   ![Situation Overview Snapshot](docs/screenshots/situation_overview_snapshot.png)

2. **Situation Overview — Overall Situation Report** — On-demand deterministic report with interpretation, priority zones, and transfers.

   ![Situation Overview Report](docs/screenshots/situation_overview_report.png)

3. **Priority Needs** — Critical shortages ranked by mismatch score and urgency.

   ![Priority Needs](docs/screenshots/priority_needs.png)

4. **Available Surplus** — Surplus zones and resources that may support redistribution.

   ![Available Surplus](docs/screenshots/available_surplus.png)

5. **Resource Balance** — Net supply-demand gaps by resource type.

   ![Resource Balance](docs/screenshots/resource_balance.png)

6. **Operational Map** — Zone markers colored by mismatch status with zone selection.

   ![Operational Map](docs/screenshots/operational_map.png)

7. **Resource Transfer Recommendations** — Same-country and fallback transfer candidates for the selected zone.

   ![Transfer Recommendations](docs/screenshots/transfer_recommendations.png)

8. **Zone Operational Brief** — Template-based operational briefing for a selected crisis zone.

   ![Zone Operational Brief](docs/screenshots/zone_operational_brief.png)

9. **Retrieved Crisis Context** — Hybrid RAG results from ReliefWeb/GDACS records with fallback labeling.

   ![RAG Context Expanded](docs/screenshots/rag_context_expanded.png)

10. **AI-Assisted Briefing** — Optional local Ollama draft labeled for coordinator review.

    ![AI Assisted Briefing](docs/screenshots/ai_assisted_briefing.png)

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

## How to Run Locally

### 1. Create venv and install requirements

```bash
cd CrisisResourceIntel
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure `.env`

```bash
cp .env.example .env
```

Set `RELIEFWEB_APPNAME` (ReliefWeb v2 requires a [pre-approved appname](https://apidoc.reliefweb.int/parameters#appname)), `DATABASE_URL`, `API_BASE_URL` (default `http://127.0.0.1:8001`), and `POSTGRES_PORT` (**5433**, matching `docker-compose.yml`). See [docs/env_setup.md](docs/env_setup.md).

### 3. Start Docker database

```bash
docker compose up -d
python -m database.test_connection
```

Docker uses the **pgvector/pgvector** image and maps host port **5433** to container port **5432**.

### 4. Run ingestion, cleaning, and loading scripts

Ingest public crisis data:

```bash
python -m ingestion.reliefweb_ingest
python -m ingestion.gdacs_ingest
```

Clean and load into PostgreSQL:

```bash
python -m ingestion.clean_reliefweb
python -m ingestion.clean_gdacs
python -m database.load_reports
```

Generate and load simulated resource data:

```bash
python -m database.generate_sample_resources
python -m database.load_resources
python -m analytics.mismatch_engine
```

| Table | Source |
|-------|--------|
| `crisis_reports` | `data/processed/reliefweb_reports_clean.csv` |
| `gdacs_alerts` | `data/processed/gdacs_alerts_clean.csv` |
| `organizations`, `zones`, `resource_inventory`, `resource_requests` | Simulated sample data |
| `mismatch_scores` | Derived from inventory and requests |

### 5. Start FastAPI

```bash
uvicorn backend.main:app --reload --port 8001
```

- Interactive docs: http://127.0.0.1:8001/docs
- Health check: http://127.0.0.1:8001/health

### 6. Start Streamlit

In a second terminal:

```bash
streamlit run dashboard/app.py
```

Dashboard URL: http://localhost:8501

### 7. Optional: Ollama and RAG setup

Required for **full local demo mode** with semantic RAG retrieval and AI-assisted briefings:

```bash
ollama pull nomic-embed-text
ollama pull llama3.2
ollama serve

python -m rag.build_corpus
python -m rag.chunk_documents
python -m database.create_rag_tables
python -m rag.embed_chunks
```

On the hosted Render demo, keyword-based retrieved crisis context is available without Ollama when `rag_chunks` data is loaded in PostgreSQL.

## Hosted Deployment

This project is deployed as a portfolio demo using [Render](https://render.com/):

| Component | Hosting |
|-----------|---------|
| FastAPI backend | Render Web Service |
| Streamlit dashboard | Render Web Service |
| PostgreSQL database | Render PostgreSQL |
| Local development database | Docker Compose with PostgreSQL + pgvector |
| Local AI/RAG mode | Ollama with `nomic-embed-text` and `llama3.2` |

**Live URLs:**

- Dashboard: [https://crisis-resource-dashboard.onrender.com](https://crisis-resource-dashboard.onrender.com)
- API docs: [https://crisis-resource-api.onrender.com/docs](https://crisis-resource-api.onrender.com/docs)

**Hosted behavior:**

- The dashboard reads from the deployed FastAPI API using `API_BASE_URL`.
- The backend reads from Render PostgreSQL using `DATABASE_URL`.
- The hosted dashboard supports keyword-based retrieved crisis context when local Ollama semantic retrieval is unavailable.
- AI-assisted briefings remain available in local demo mode with Ollama.

**Render start commands:**

FastAPI backend:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

Streamlit dashboard:

```bash
streamlit run dashboard/app.py --server.port $PORT --server.address 0.0.0.0
```

**Environment variables (no secrets in this README):**

| Service | Variable | Purpose |
|---------|----------|---------|
| Backend | `DATABASE_URL` | Render PostgreSQL connection string |
| Backend | `RELIEFWEB_APPNAME` | ReliefWeb ingestion (if run from hosted service) |
| Dashboard | `API_BASE_URL` | Public URL of the deployed FastAPI service |

Local default for `API_BASE_URL`: `http://127.0.0.1:8001`.

**Data loading for hosted demos:**

- Load crisis data, simulated resources, mismatch scores, and RAG chunks into the Render PostgreSQL instance before presenting the hosted dashboard.
- RAG features require `rag_chunks` records in the deployed database; semantic search additionally requires embeddings for full local hybrid mode.

## API Endpoints

| Prefix | Description |
|--------|-------------|
| `/crises` | ReliefWeb reports and GDACS alerts |
| `/resources` | Zones, organizations, inventory, requests |
| `/mismatches` | Shortage/surplus analytics, reallocation recommendations, and OR-Tools optimized transfers |
| `/reports` | KPI overview, situation report, shortage-risk forecast, zone briefings, and supporting RAG context / AI briefings |

Key routes:

- `GET /health` — API and database connectivity
- `GET /reports/overview` — System KPIs
- `GET /reports/situation-report` — Deterministic overall situation report
- `GET /reports/zone-briefing/{zone_id}` — Consolidated zone briefing JSON
- `GET /reports/rag-zone-context/{zone_id}` — Hybrid-retrieved ReliefWeb/GDACS context
- `GET /reports/ai-zone-briefing/{zone_id}` — Optional local LLM-assisted draft briefing
- `GET /reports/shortage-risk-forecast` — ML 48–72 hour shortage-risk forecast (prototype, proxy labels)
- `GET /mismatches/critical` — Critical shortages
- `GET /mismatches/surplus` — Surplus resources
- `GET /mismatches/reallocation-recommendations` — Deterministic transfer recommendations
- `GET /mismatches/optimized-transfers` — OR-Tools optimized transfer plan (simulated cost units)

Examples (local):

- http://127.0.0.1:8001/reports/zone-briefing/ZONE001
- http://127.0.0.1:8001/reports/situation-report
- http://127.0.0.1:8001/reports/rag-zone-context/ZONE001
- http://127.0.0.1:8001/mismatches/reallocation-recommendations
- http://127.0.0.1:8001/mismatches/optimized-transfers
- http://127.0.0.1:8001/reports/shortage-risk-forecast

Examples (hosted):

- https://crisis-resource-api.onrender.com/reports/zone-briefing/ZONE001
- https://crisis-resource-api.onrender.com/reports/situation-report
- https://crisis-resource-api.onrender.com/reports/rag-zone-context/ZONE001
- https://crisis-resource-api.onrender.com/mismatches/reallocation-recommendations
- https://crisis-resource-api.onrender.com/mismatches/optimized-transfers
- https://crisis-resource-api.onrender.com/reports/shortage-risk-forecast

## Methodology

### Data sources

| Source | Description |
|--------|-------------|
| [ReliefWeb API](https://apidoc.reliefweb.int/) | Humanitarian reports and situation updates |
| [GDACS](https://www.gdacs.org/) | Disaster alerts and crisis event metadata |

### Supply-demand mismatch scoring

`analytics/mismatch_engine.py` compares available supply against requested demand by zone and resource type. It calculates shortage gap, shortage ratio, urgency weight, and mismatch score (`shortage gap × urgency weight`), then assigns status labels: surplus, stable, moderate shortage, severe shortage, or critical shortage.

```bash
python -m analytics.mismatch_engine
```

SQL query templates for shortages, surpluses, and summaries live in `analytics/queries/`.

### Resource reallocation recommendations

`analytics/reallocation_engine.py` matches shortage zones to surplus zones by resource type.

- **Same-country transfer candidates** are prioritized first (higher confidence).
- **Cross-country fallback candidates** are included when needed and labeled lower-confidence.
- Each recommendation includes quantity, source zone, destination zone, confidence level, match type, and a feasibility note.

The Operational Map dashboard shows prioritized transfers for the selected destination zone, with an expander for all recommendations.

### OR-Tools optimized transfer planning

`analytics/optimization_engine.py` complements the deterministic engine with a constrained minimum-cost transport model using Google OR-Tools.

- Surplus zones are supply nodes; shortage zones are demand nodes, matched by `resource_type`
- The solver minimizes **simulated transport cost** (relative cost units) while prioritizing demand fulfillment via unmet-demand penalties
- Same-country routes use lower simulated unit costs; cross-country fallback routes use higher costs
- Optimization cost is based on simulated distance and logistics assumptions for demonstration purposes. Values are relative cost units, not real-world USD estimates.
- Results are exposed at `GET /mismatches/optimized-transfers` and shown in the dashboard **Optimized Transfer Plan** section

### Shortage risk forecasting (ML layer)

The `ml_forecasting/` package adds a lightweight machine-learning **forecasting/risk-classification layer** on top of the analytics and optimization systems. It predicts **48–72 hour shortage severity risk** (`low` / `medium` / `high` / `critical`) per zone and resource type.

- **Features** combine crisis/resource signals: crisis type, country, resource type, shortage gap, requested vs. available quantity, fulfillment ratio, urgency score, mismatch score, and country-level GDACS alert and crisis-report counts (`ml_forecasting/feature_builder.py`). Missing values use safe defaults (`crisis_type='unknown'`, counts `0`, urgency `low`).
- **Labels are simulated/proxy labels.** Real NGO demand-outcome labels are not publicly available, so `shortage_risk_level` is derived transparently from shortage gap, fulfillment ratio, urgency, mismatch score, and resource criticality.
- **Model:** XGBoost (`XGBClassifier`) when available, with a scikit-learn `RandomForestClassifier` fallback, inside a one-hot preprocessing pipeline, saved to `models/shortage_risk_model.joblib` (`ml_forecasting/train_model.py`).
- **Prediction** returns the predicted risk level, 48h/72h horizon risk (72h escalates one level when a shortage persists and is under-fulfilled), a confidence score, global top contributing features, and a method note (`ml_forecasting/predict_risk.py`).
- This layer **supports early planning and is not an automated decision-maker.** It complements — and does not replace — the OR-Tools optimization plan or human judgment.

Build, train, and inspect locally:

```bash
python -m ml_forecasting.feature_builder
python -m ml_forecasting.train_model
python -m ml_forecasting.predict_risk
```

Results are exposed at `GET /reports/shortage-risk-forecast` and shown in the dashboard **Shortage Risk Forecast** tab. If the trained model or feature data is unavailable, the endpoint returns a graceful message instead of failing.

### Overall Situation Report

`GET /reports/situation-report` returns a deterministic, template-based report across all zones. It is **not LLM-generated**. The report summarizes top priority zones, critical shortages, recommended transfers, recommended actions, operational interpretation, and limitations.

In the Situation Overview tab, users click **Generate Situation Report** to fetch it on demand. Operational Snapshot KPI cards remain the main dashboard metrics; the report section focuses on interpretation and operational detail.

### Map-based zone operational briefs

The Operational Map supports selected-zone briefing preview. Users select a zone, review a compact **Selected Zone** panel, then choose to view the **Zone Operational Brief**, download a PDF, or open copy-ready text.

Template-based briefs are the **stable default**—deterministic and grounded in PostgreSQL data. PDF export is optional via ReportLab (`pip install reportlab`).

### Hybrid RAG retrieval

Retrieved crisis context uses hybrid semantic + keyword search over ReliefWeb/GDACS chunks stored in PostgreSQL with pgvector when Ollama is available locally. Results are boosted by country, event type, and source metadata. If too few country-specific records match, fallback results are included and labeled `is_fallback: true`.

On the hosted Render demo, when Ollama is unavailable, the API falls back to keyword/metadata retrieval from `rag_chunks` in PostgreSQL and labels results with `retrieval_mode: keyword_fallback`.

### Local LLM-assisted briefings

AI-assisted operational briefings are generated **locally** using Ollama `llama3.2`. The prompt is grounded in structured zone metrics and retrieved context:

- The zone's related disaster alert is the **primary event**
- Retrieved sources are **supporting context only**
- The model is instructed **not to invent facts**
- The dashboard labels output as an **AI-assisted draft requiring review**

AI briefings are optional and on-demand. They do not replace template briefs, PDF export, or copy actions.

## Limitations

This is a **portfolio prototype**, not a production emergency response system:

- Operational inventory and resource request data are **simulated prototype data**, not real NGO supply systems
- Public humanitarian records depend on ReliefWeb and GDACS availability and coverage
- **Transfer recommendations must be validated by field coordinators** before dispatch
- **Cross-country fallback transfers** require customs, logistics, and partner review before action
- AI-assisted briefings are **drafts** and should be reviewed before any operational use
- The system does not make final operational decisions and should not be presented as production-ready

### Data Limitations and Real-World Deployment

This prototype uses real public crisis data from ReliefWeb and GDACS, combined with simulated operational inventory, request, and transport-cost data. Real NGO inventory and field-request data is usually private because it may reveal sensitive stock levels, warehouse locations, medical supplies, and security-relevant logistics constraints. In a production deployment, the simulated operational tables could be replaced with authenticated NGO ERP, warehouse, or logistics APIs. Key challenges would include data quality, delayed field reporting, duplicate requests, inconsistent item naming, inventory synchronization, access control, customs/security constraints, road closures, and delivery-capacity limits.

## Development Timeline

| Phase | Delivered |
|-------|-----------|
| Week 1 | Project setup; ReliefWeb and GDACS ingestion to `data/raw/` |
| Week 2 | Cleaning scripts, PostgreSQL schema, loader for `crisis_reports` and `gdacs_alerts` |
| Week 3 | Simulated organizations, zones, inventory, requests; mismatch scoring engine |
| Week 4 | FastAPI backend exposing crises, resources, mismatches, and reports |
| Week 5 | Streamlit dashboard with situation overview, priority needs, surplus, balance, and operational map |
| Week 6 Part 1 | Zone briefing endpoint; map-based template operational briefs with PDF/copy export |
| Week 6 Part 2 | pgvector RAG corpus, hybrid retrieval, optional Ollama AI briefings, demo health check |
| Extensions | Resource reallocation recommendations; Overall Situation Report; dashboard polish; Render deployment |
| Enhancement | Google OR-Tools optimized transfer planning (`GET /mismatches/optimized-transfers`) |
| Current enhancement | ML shortage-risk forecasting layer (`GET /reports/shortage-risk-forecast`) |

## Future Work

Beyond the current portfolio demo, production-oriented next steps would focus on:

- Real NGO ERP / logistics integrations to replace simulated operational tables
- Authenticated partner data pipelines with access control
- Real-time scheduled ingestion of crisis and resource updates
- Geospatial routing with road-closure and security constraints
- Human-in-the-loop validation workflows for transfers and forecasts
- Model evaluation on real historical partner data where available

## Current Enhancement: OR-Tools Optimized Transfers

The **Optimized Transfer Plan** complements baseline deterministic reallocation recommendations:

- **Google OR-Tools minimizes relative simulated transport cost** under supply, demand, and non-negativity constraints
- **Transfers are generated from surplus zones to shortage zones**, matched by resource type
- **Same-country routes are prioritized** where possible (lower simulated unit cost)
- **Cross-country fallback routes are allowed but labeled lower confidence** (higher simulated unit cost)
- **Cost values are relative simulated cost units, not real-world USD.** They are based on simulated distance and logistics assumptions for demonstration purposes
- **Recommendations require human validation** before operational dispatch; the optimizer does not replace field coordinator judgment

## Shortage Risk Forecasting

A lightweight ML layer that forecasts near-term shortage severity to support proactive planning:

- **Predicts 48–72 hour shortage severity** (`low` / `medium` / `high` / `critical`) for each zone and resource type.
- **Uses features** such as crisis metadata, resource type, shortage gap, fulfillment ratio, mismatch score, and urgency/severity proxies, plus country-level crisis-context counts.
- **Uses XGBoost when available, with a safe scikit-learn `RandomForestClassifier` fallback** if XGBoost cannot be loaded, so the layer degrades gracefully.
- **Trained on transparent simulated/proxy labels** derived from shortage severity, fulfillment ratio, urgency, and mismatch assumptions, because real NGO operational demand labels are not public.
- **Supports early planning and prioritization; it does not automate humanitarian decisions** and is not production-ready crisis forecasting.

> The forecasting model complements the OR-Tools optimizer: the model identifies which shortages are likely to escalate, while the optimizer recommends how available surplus resources could be transferred under supply, demand, and simulated transport-cost constraints.

Exposed at `GET /reports/shortage-risk-forecast` and the dashboard **Shortage Risk Forecast** tab (risk summary cards, a table of forecasted high/critical-risk zones, and a bar chart of predicted risk counts by level). See **Methodology → Shortage risk forecasting** for model details.

## Project Structure

```
CrisisResourceIntel/
├── .github/workflows/   # CI workflow for running tests on push and pull requests
├── ingestion/           # API fetchers, clean_reliefweb.py, clean_gdacs.py
├── database/            # Schema, loaders, sample resource generator
├── analytics/           # Mismatch scoring, reallocation, OR-Tools resource transfer optimization, SQL queries
├── ml_forecasting/      # XGBoost shortage-risk forecasting and proxy-label generation
├── models/              # Persisted ML artifacts (shortage_risk_model.joblib)
├── backend/             # FastAPI application
├── dashboard/           # Streamlit UI
├── scripts/             # Demo health check and utilities
├── rag/                 # Corpus, embeddings, hybrid retrieval, LLM briefing
├── data/                # Raw, processed, and sample data
├── docs/                # Architecture and dev notes
├── docs/architecture/   # architecture diagram source and rendered assets
└── tests/               # pytest suite for API, analytics, optimization, ML forecasting, RAG fallback, and config checks
```

## Running Tests

```bash
pytest
```

The suite is lightweight and runs locally without external APIs, Render services, or Ollama:

- **API tests** use FastAPI's `TestClient` (root and `/health` always run; `/reports/overview`, `/mismatches/optimized-transfers`, and `/reports/shortage-risk-forecast` skip or fall back gracefully when PostgreSQL or sample data is unavailable).
- **Analytics tests** cover the mismatch and reallocation engines as pure functions (shortage/surplus/stable status, urgency weighting, same-country vs. cross-country confidence, resource-type matching).
- **Optimization tests** validate the OR-Tools engine result shape and constraints, skipping if `ortools` is not installed.
- **ML forecasting tests** cover feature-builder output, proxy-label creation, the XGBoost/proxy prediction output schema (valid risk levels, confidence in `[0, 1]`), and graceful fallback when the model artifact is missing — all using in-memory data (no database or live services), skipping model-dependent checks if scikit-learn is unavailable.
- **RAG fallback tests** exercise keyword/hosted-mode context building without Ollama.
- **Config tests** verify API base URL resolution and that database URLs are masked so passwords are never exposed.

Database-backed tests print a clear skip message when PostgreSQL is not reachable.

## License

MIT License
