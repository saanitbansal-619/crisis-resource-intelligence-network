# Interview Notes — Crisis Resource Intelligence Network

Interview prep guide for explaining this project to recruiters, professors, and technical interviewers.

---

## 1. 30-Second Pitch

I built a full-stack crisis resource intelligence platform that ingests public disaster alerts and humanitarian reports from GDACS and ReliefWeb, stores structured data in PostgreSQL, computes zone-level supply-demand mismatch scores using simulated NGO resource data, and presents priority needs through a FastAPI-backed Streamlit dashboard with operational map briefings.

---

## 2. Project Problem

Crisis response teams need to quickly understand:

- where disasters are happening
- what resources are needed
- where shortages exist
- where surplus capacity could be redistributed

Public crisis data is available, but turning alerts and reports into actionable resource intelligence requires ingestion, normalization, analytics, and accessible decision-support tools. This project addresses that gap.

---

## 3. Why I Built It

The project demonstrates end-to-end skills across:

- data ingestion from real APIs
- database design and loading
- backend API development
- analytics and scoring logic
- dashboard design for non-technical stakeholders
- humanitarian decision-support workflows
- a foundation for future AI/RAG integration

It is structured as a portfolio system that shows I can move from raw external data to a usable operational interface.

---

## 4. System Architecture Explanation

Pipeline:

```
ReliefWeb API + GDACS RSS
    → ingestion scripts
    → processed CSVs
    → PostgreSQL
    → mismatch scoring engine
    → FastAPI backend
    → Streamlit dashboard
    → operational map and zone briefings
```

**Ingestion:** Python scripts fetch ReliefWeb reports and GDACS alerts and save raw outputs.

**Cleaning:** Scripts normalize dates, flatten fields, and write processed CSVs.

**Database:** PostgreSQL stores crisis reports, alerts, zones, organizations, inventory, requests, and mismatch scores.

**Analytics:** The mismatch engine compares supply vs. demand and writes scored results.

**Backend:** FastAPI exposes REST endpoints for crises, resources, mismatches, and reports.

**Dashboard:** Streamlit consumes the API and presents KPIs, charts, maps, and zone briefings.

---

## 5. Real vs Simulated Data

### Real / public data

- **GDACS** disaster alerts
- **ReliefWeb** humanitarian reports

### Simulated data

- NGO organizations
- resource inventory by zone
- zone-level resource requests

### Why simulate resources?

Real NGO inventory and request data is usually not public due to privacy, security, and operational sensitivity. I simulated this layer to prototype the schema, analytics workflow, and dashboard while still grounding the system in real public crisis data.

**Important:** Do not present simulated inventory or requests as real operational NGO data in interviews or demos.

---

## 6. Mismatch Score Explanation

The mismatch engine compares available supply against requested demand for each zone and resource type.

It calculates:

| Metric | Meaning |
|--------|---------|
| **Shortage gap** | `needed - available` |
| **Shortage ratio** | `shortage gap / needed` |
| **Urgency weight** | Based on request urgency level (e.g. low, medium, high, critical) |
| **Mismatch score** | `shortage gap × urgency weight` |

Status labels:

- critical shortage
- severe shortage
- moderate shortage
- stable
- surplus

Higher mismatch scores indicate larger, more urgent gaps that may need priority coordination. The scoring is transparent and rule-based, which matters for humanitarian use cases where coordinators need explainable outputs.

---

## 7. Backend Explanation

FastAPI exposes analytics and database outputs through REST endpoints. This separates the dashboard from the database and makes the project easier to extend with future frontends, mobile apps, or AI/RAG services.

**Key endpoints:**

| Endpoint | Purpose |
|----------|---------|
| `/health` | API and database connectivity check |
| `/reports/overview` | System KPIs |
| `/reports/resource-summary` | Resource-type mismatch summary |
| `/reports/zone-briefing/{zone_id}` | Consolidated zone briefing JSON |
| `/mismatches/critical` | Critical shortages |
| `/mismatches/surplus` | Surplus resources |
| `/resources/zones` | Crisis response zones |
| `/crises/alerts` | GDACS alerts |
| `/crises/reports` | ReliefWeb reports |

The zone briefing endpoint consolidates zone metadata, priority needs, surplus, inventory, requests, related GDACS alerts, and summary metrics in one structured response.

---

## 8. Dashboard Explanation

The Streamlit dashboard is designed for humanitarian stakeholders, not developers. It uses a light, professional NGO-oriented visual style with readable labels and muted severity colors.

**Tabs:**

- **Situation Overview** — KPIs, workflow explanation, data sources
- **Priority Needs** — critical shortages, tables, charts
- **Available Surplus** — surplus zones and redistribution candidates
- **Resource Balance** — net gaps by resource type
- **Operational Map** — zone markers by mismatch status, zone selection, operational briefings

**Operational Map workflow:**

1. User selects a zone on the map or via dropdown.
2. A **Selected Zone** summary card appears.
3. User clicks **View Operational Brief** to open the full preview.
4. User can **Download PDF** or **Copy Brief** (clipboard) from export actions below the brief.

The dashboard calls the FastAPI backend internally; it does not connect directly to PostgreSQL.

---

## 9. Zone Operational Briefing Explanation

The current briefing is **template-based** and grounded in structured database/API outputs from `GET /reports/zone-briefing/{zone_id}`.

Each brief summarizes:

- zone overview (name, location, population)
- related disaster alert (when linked via `crisis_event_id`)
- priority resource gaps
- available inventory and partner organizations
- resource requests
- operational interpretation and recommended actions
- data transparency note (public vs simulated sources)

I built the briefing workflow on the **Operational Map** so reports are generated in geographic context. Before adding LLMs, I wanted deterministic, explainable outputs tied to PostgreSQL metrics.

---

## 10. Is This RAG?

**Partially — retrieval baseline only.**

The dashboard briefing is still template-based. A first RAG layer now exists offline in the `rag/` package:

- builds a corpus from ReliefWeb and GDACS rows in PostgreSQL
- chunks report/alert text locally
- retrieves relevant passages with TF-IDF keyword search

It does **not** yet use embeddings, pgvector, Ollama, OpenAI, or LLM generation.

**Planned next RAG steps:**

- pgvector semantic search and hybrid retrieval
- local LLM-generated briefings grounded in SQL metrics + retrieved context

The zone briefing endpoint and mismatch scores are designed to keep future AI outputs anchored to structured data rather than free-form generation alone.

---

## RAG Layer Status

The first RAG layer builds a local searchable corpus from ReliefWeb and GDACS records stored in PostgreSQL. It chunks report/alert text and uses TF-IDF retrieval to find relevant crisis context for a selected zone. This is a lightweight retrieval baseline before adding pgvector semantic search, hybrid retrieval, or local LLM-generated briefings.

The RAG layer now exposes a FastAPI endpoint for zone-specific retrieved crisis context, allowing the dashboard to later display retrieved ReliefWeb/GDACS context alongside structured shortage metrics.

**API endpoint:** `GET /reports/rag-zone-context/{zone_id}`

The next RAG phase adds pgvector-enabled PostgreSQL so the system can store embeddings for ReliefWeb/GDACS chunks and support semantic search alongside keyword/metadata retrieval.

The project now includes a pgvector-backed semantic retrieval phase. ReliefWeb/GDACS chunks can be embedded locally using Ollama `nomic-embed-text` and stored in PostgreSQL with `vector(768)`. This enables semantic search over crisis context while keeping the earlier TF-IDF retriever as a baseline/fallback.

**Offline commands:**

```bash
python -m rag.build_corpus
python -m rag.chunk_documents
python -m rag.simple_retriever "Philippines earthquake water food medical needs"
python -m database.create_rag_tables
python -m rag.embed_chunks
python -m rag.semantic_retriever "Philippines earthquake water food medical needs"
```

---

## 11. What I Would Improve Next

- RAG-based briefings over ReliefWeb/GDACS text
- scheduled ingestion with Airflow
- demand forecasting / ML shortage-risk models
- cloud deployment (e.g. containerized API + managed PostgreSQL)
- authentication and role-based access
- integration with real NGO inventory systems (with proper data agreements)
- better geospatial matching between alerts and zones
- improved alert-to-zone linking and normalization

---

## 12. Common Interview Questions and Answers

### Q: Why did you simulate NGO resource data?

**A:** Because real NGO inventory data is not generally public, but simulating it allowed me to design the schema, analytics, and dashboard workflow while still using real public crisis data from GDACS and ReliefWeb.

### Q: Why FastAPI instead of connecting Streamlit directly to PostgreSQL?

**A:** FastAPI separates the backend from the frontend, makes the system more modular, and allows the same data layer to support future apps, AI services, or external integrations without rewriting database logic in the UI.

### Q: How is priority determined?

**A:** Priority is based on shortage gap, shortage ratio, and urgency weighting. Larger gaps with higher urgency receive higher mismatch scores. Results are labeled as critical, severe, moderate, stable, or surplus.

### Q: What was the hardest technical part?

**A:** Coordinating the full pipeline—ingestion, cleaning, database loading, mismatch scoring, API endpoints, and the frontend dashboard—while keeping the data model and zone/alert relationships consistent across layers.

### Q: How would this become production-ready?

**A:** Add scheduled ingestion, authentication, cloud deployment, monitoring, real organization data integrations (with proper agreements), and stronger geospatial and event-to-zone matching.

### Q: What makes this more than a dashboard?

**A:** It includes a backend API, PostgreSQL schema, ingestion pipeline, analytics/scoring layer, and an operational reporting workflow—not just charts on top of a CSV.

### Q: Is the briefing AI-generated?

**A:** No. It is template-based today, built from structured API/database outputs. RAG/LLM enrichment is a planned next step, with SQL metrics kept as the grounding layer.

### Q: How do you link zones to GDACS alerts?

**A:** Zones store a `crisis_event_id` that is matched to `gdacs_alerts.alert_id`, with normalization for ID format differences (e.g. `1544854.0` vs `1544854`).

---

## Quick Demo Flow (2–3 minutes)

1. Show **Situation Overview** KPIs and explain data sources.
2. Open **Priority Needs** — point out highest mismatch scores.
3. Open **Operational Map** — select a zone, view **Selected Zone** panel.
4. Click **View Operational Brief** — walk through priority gaps and related alert.
5. Mention **Download PDF** / **Copy Brief** as export options.
6. Optionally open `/docs` on the FastAPI backend to show the API layer.

---

## Tone Reminders

- Be accurate about what is real vs simulated.
- Do not overhype AI capabilities—the briefing is template-based today.
- Emphasize explainability and decision support for humanitarian coordination.
- Do not share `.env` values, credentials, or internal database passwords in interviews.
