# Interview Notes — Crisis Resource Intelligence Network

Interview prep guide for explaining this project to recruiters, professors, and technical interviewers.

---

## 1. 30-Second Pitch

I built a full-stack crisis resource intelligence platform that ingests public disaster alerts and humanitarian reports from GDACS and ReliefWeb, stores structured data in PostgreSQL, computes zone-level supply-demand mismatch scores using simulated NGO resource data, generates deterministic transfer recommendations and an overall situation report, and presents priority needs through a FastAPI-backed Streamlit dashboard. The Operational Map includes template zone briefings, hybrid RAG retrieval over ReliefWeb/GDACS records with pgvector, optional local LLM-assisted draft briefings via Ollama, and resource transfer recommendations.

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
- retrieval-augmented context and local LLM draft generation

It is structured as a portfolio system that shows I can move from raw external data to a usable operational interface.

### Final system status

- Full dashboard workflow is complete
- Hybrid RAG retrieval is complete
- Local LLM briefing generation is complete
- Resource reallocation recommendations are complete
- Overall Situation Report (deterministic) is complete
- Dashboard error handling was added for demo reliability
- Screenshots and demo recording are the remaining presentation tasks

This remains a portfolio prototype, not a production emergency response system.

---

## 4. System Architecture Explanation

Pipeline:

```
ReliefWeb/GDACS ingestion
    → PostgreSQL storage
    → mismatch scoring
    → transfer recommendation engine
    → hybrid RAG retrieval with pgvector
    → optional local Ollama AI briefing
    → dashboard situation report and operational map
```

**RAG pipeline:**

```
ReliefWeb/GDACS records
    → corpus building → chunking
    → Ollama nomic-embed-text embeddings
    → PostgreSQL pgvector storage
    → hybrid semantic + keyword retrieval + metadata boosting
    → fallback labeling
    → optional Ollama llama3.2 AI-assisted briefing
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
| `/reports/situation-report` | Deterministic overall situation report (not LLM-generated) |
| `/reports/resource-summary` | Resource-type mismatch summary |
| `/reports/zone-briefing/{zone_id}` | Consolidated zone briefing JSON (template) |
| `/reports/rag-zone-context/{zone_id}` | Hybrid-retrieved ReliefWeb/GDACS context |
| `/reports/ai-zone-briefing/{zone_id}` | Optional local LLM-assisted draft briefing |
| `/mismatches/critical` | Critical shortages |
| `/mismatches/surplus` | Surplus resources |
| `/mismatches/reallocation-recommendations` | Deterministic surplus-to-shortage transfer recommendations |
| `/resources/zones` | Crisis response zones |
| `/crises/alerts` | GDACS alerts |
| `/crises/reports` | ReliefWeb reports |

The zone briefing endpoint consolidates zone metadata, priority needs, surplus, inventory, requests, related GDACS alerts, and summary metrics in one structured response.

---

## 8. Dashboard Explanation

The Streamlit dashboard is designed for humanitarian stakeholders, not developers. It uses a light, professional NGO-oriented visual style with readable labels and muted severity colors.

**Tabs:**

- **Situation Overview** — KPIs, workflow explanation, data sources, on-demand Overall Situation Report
- **Priority Needs** — critical shortages, tables, charts
- **Available Surplus** — surplus zones and redistribution candidates
- **Resource Balance** — net gaps by resource type
- **Operational Map** — zone markers by mismatch status, zone selection, operational briefings, transfer recommendations

**Operational Map workflow:**

1. User selects a zone on the map or via dropdown.
2. A **Selected Zone** summary card appears.
3. User clicks **View Operational Brief** to open the template brief preview.
4. Retrieved **Crisis Context** loads from ReliefWeb/GDACS records (hybrid RAG).
5. User can optionally click **Generate AI-Assisted Brief** for a local Ollama draft.
6. User can **Download PDF** or **Copy Brief** (clipboard) from export actions below the template brief.

The dashboard calls the FastAPI backend internally; it does not connect directly to PostgreSQL. Template briefs remain the stable default. AI output is labeled as a draft requiring review.

---

## 9. Zone Operational Briefing Explanation

The **template-based** briefing is the stable default. It is grounded in structured database/API outputs from `GET /reports/zone-briefing/{zone_id}`.

Each template brief summarizes:

- zone overview (name, location, population)
- related disaster alert (when linked via `crisis_event_id`)
- priority resource gaps
- available inventory and partner organizations
- resource requests
- operational interpretation and recommended actions
- data transparency note (public vs simulated sources)

I built the briefing workflow on the **Operational Map** so reports are generated in geographic context. Template outputs are deterministic and explainable before any AI layer is invoked.

### Retrieved crisis context

After viewing the template brief, the dashboard fetches hybrid-retrieved ReliefWeb/GDACS context via `GET /reports/rag-zone-context/{zone_id}`. This is retrieval-based supporting context—not an LLM analysis.

### Optional AI-assisted draft

Users can optionally generate a local LLM draft via `GET /reports/ai-zone-briefing/{zone_id}` (Ollama `llama3.2`). The related disaster alert is the primary event; retrieved sources are supporting context only. The dashboard labels this output as an AI-assisted draft requiring review.

---

## 9a. Resource Reallocation Recommendations

The transfer recommendation engine compares shortage zones against surplus zones by resource type using mismatch scores and simulated inventory/request data.

**How to explain it in an interview:**

> The system matches surplus capacity to shortage gaps deterministically. Same-country transfers are prioritized because they are more feasible. Cross-country options are included as lower-confidence fallbacks with explicit feasibility notes. Every recommendation includes quantity, source zone, destination zone, confidence level, match type, and a validation note—but coordinators still need to confirm transport, access, and partner availability before dispatch.

**Key behaviors:**

| Behavior | Detail |
|----------|--------|
| Matching logic | Shortage records matched to surplus by resource type |
| Prioritization | Same-country candidates first; cross-country fallback when needed |
| Confidence | Higher for same-country; lower for cross-country fallback |
| Output fields | Quantity, from/to zones, confidence, match type, feasibility note |
| Validation | Recommendations require field coordinator review before use |

**API:** `GET /mismatches/reallocation-recommendations`

The Operational Map dashboard shows prioritized transfers for the selected destination zone plus an expander for all recommendations.

---

## 9b. Overall Situation Report

The **Overall Situation Report** is a deterministic, template-based portfolio report across all zones. It is **not LLM-generated**.

**API:** `GET /reports/situation-report`

It summarizes:

- top priority zones (by mismatch score, shortage gap, urgency)
- critical shortages
- recommended transfers
- recommended actions
- operational interpretation (template-generated paragraph)
- limitations and method note

The dashboard **Situation Overview** tab includes a **Generate Situation Report** button. The report is fetched on demand only—not auto-generated on page load. Operational Snapshot KPI cards remain the main metrics area; the report section focuses on interpretation and operational detail.

---

## 10. RAG and Local LLM Explanation

**Yes — the project includes a working RAG layer and optional local LLM briefing.**

### How to explain it in an interview

> The RAG system first retrieves relevant crisis records using pgvector semantic search and keyword scoring. It then applies metadata boosts for country and event type so that a zone in the Philippines retrieves Philippines earthquake context rather than generic disaster records. If too few country-specific records exist, fallback results are included but clearly labeled. A local Ollama LLM can then generate an AI-assisted operational draft from the structured zone metrics and retrieved context.

### RAG pipeline

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

### Key design choices

| Choice | Rationale |
|--------|-----------|
| Hybrid retrieval | Semantic search catches meaning; TF-IDF catches exact terms; metadata boost aligns results to zone country/event |
| Fallback labeling | When country-specific coverage is thin, general records are included but marked `is_fallback: true` |
| Primary alert grounding | The zone's related GDACS alert is the primary event; retrieved context is supporting only |
| Local Ollama | No external API keys; drafts run on the developer machine |
| Template brief as default | Deterministic, explainable output remains the stable coordination brief |

### API endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /reports/rag-zone-context/{zone_id}` | Hybrid-retrieved ReliefWeb/GDACS context |
| `GET /reports/ai-zone-briefing/{zone_id}` | Optional local LLM-assisted draft |

### Offline setup commands

```bash
ollama pull nomic-embed-text
ollama pull llama3.2
python -m rag.build_corpus
python -m rag.chunk_documents
python -m database.create_rag_tables
python -m rag.embed_chunks
python -m rag.hybrid_retriever "Philippines earthquake water food medical needs"
```

### Limitations (be honest in interviews)

- Operational inventory and resource request data are **simulated prototype data**
- Public humanitarian records are limited to ReliefWeb and GDACS coverage
- **Transfer recommendations must be validated by field coordinators** before dispatch
- **Cross-country fallback transfers** require customs, logistics, and partner review
- AI-assisted briefings are **drafts** and should be reviewed before operational use
- This is a **portfolio prototype**, not a production emergency response system
- Do not present the system as production-ready or imply real NGO inventory access
- The AI does not make final operational decisions

---

## 11. What I Would Improve Next

- scheduled ingestion with Airflow
- demand forecasting / ML shortage-risk models
- cloud deployment (e.g. containerized API + managed PostgreSQL)
- authentication and role-based access
- integration with real NGO inventory systems (with proper data agreements)
- better geospatial matching between alerts and zones
- improved alert-to-zone linking and normalization
- stronger evaluation of RAG retrieval quality across more crisis types

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

**A:** The **default** operational brief is template-based, built from structured API/database outputs. Optionally, users can generate a **local LLM-assisted draft** via Ollama `llama3.2`, grounded in zone metrics and retrieved ReliefWeb/GDACS context. The dashboard labels that output as a draft requiring review. The AI does not make final operational decisions.

### Q: How does the RAG layer work?

**A:** ReliefWeb and GDACS records are chunked and embedded with Ollama `nomic-embed-text`, stored in PostgreSQL with pgvector, and retrieved with hybrid semantic + TF-IDF keyword scoring plus metadata boosts for country and event type. Fallback results are labeled when country-specific coverage is thin. Retrieved context supports—but does not replace—the zone's primary disaster alert in AI drafts.

### Q: How do you link zones to GDACS alerts?

**A:** Zones store a `crisis_event_id` that is matched to `gdacs_alerts.alert_id`, with normalization for ID format differences (e.g. `1544854.0` vs `1544854`).

### Q: How do transfer recommendations work?

**A:** The reallocation engine matches surplus zones to shortage zones by resource type using mismatch scores. Same-country candidates are prioritized with higher confidence. Cross-country fallbacks are labeled lower-confidence and include feasibility notes about customs, transport, and partner approval. All recommendations are deterministic and based on simulated data—they still require field validation.

### Q: Is the Overall Situation Report AI-generated?

**A:** No. It is a deterministic, template-based report built from mismatch scores, resource gaps, surplus records, and transfer recommendation logic. The dashboard fetches it on demand via `GET /reports/situation-report`. It complements—but does not replace—the optional zone-level AI-assisted brief on the Operational Map.

---

## Demo Health Check

Before a dashboard demo or interview walkthrough, run:

```bash
python -m scripts.health_check
```

Expected output when everything is running:

```
[OK] Database connection
[OK] FastAPI backend
[OK] RAG context endpoint
[OK] AI briefing endpoint
```

What each check verifies:

| Check | Verifies |
|-------|----------|
| Database connection | PostgreSQL connection using `DATABASE_URL` |
| FastAPI backend | API availability at `http://127.0.0.1:8001/` |
| RAG context endpoint | Hybrid RAG retrieval for `ZONE001` |
| AI briefing endpoint | Ollama-powered draft briefing generation |

The AI briefing endpoint depends on **Ollama running locally** with **`llama3.2` available**. If Ollama is not running, the script prints a warning and the demo can still proceed with template briefs and retrieved context.

**Limitations to mention during demos:**

- Operational inventory and request data are simulated prototype data
- Transfer recommendations require field coordinator validation
- Cross-country fallback transfers need customs/logistics/partner review
- AI briefings are drafts requiring human review
- Public crisis context depends on available ReliefWeb/GDACS records
- The system does not make final operational decisions
- This is a portfolio prototype, not a production emergency response system

---

## Quick Demo Flow (2–3 minutes)

0. Run `python -m scripts.health_check` and confirm required checks pass.
1. Show **Situation Overview** KPIs and explain data sources.
2. Click **Generate Situation Report** — walk through interpretation, priority zones, shortages, transfers, and limitations.
3. Open **Priority Needs** — point out highest mismatch scores.
4. Open **Operational Map** — select a zone, view **Selected Zone** panel.
5. Show **Recommended Resource Transfers** for the selected zone.
6. Click **View Operational Brief** — walk through priority gaps and related alert.
7. Show **Retrieved Crisis Context** — explain hybrid RAG and fallback labeling.
8. Optionally click **Generate AI-Assisted Brief** — note it is a local draft requiring review.
9. Mention **Download PDF** / **Copy Brief** as export options for the template brief.
10. Optionally open `/docs` on the FastAPI backend to show situation report, reallocation, RAG, and AI endpoints.

---

## Tone Reminders

- Be accurate about what is real vs simulated.
- Template briefs are the default; AI drafts are optional and require review.
- Do not overhype AI capabilities or imply production readiness.
- Do not imply real NGO inventory access or that the AI makes final operational decisions.
- Emphasize explainability and decision support for humanitarian coordination.
- Do not share `.env` values, credentials, or internal database passwords in interviews.
