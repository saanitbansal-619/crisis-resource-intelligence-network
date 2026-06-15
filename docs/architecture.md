# Architecture

> Living document describing the Crisis Resource Intelligence Network system design.

## Overview

The platform ingests public humanitarian crisis data, stores and normalizes it in
PostgreSQL, computes supply-demand mismatches, generates deterministic transfer
recommendations and an overall situation report, exposes results via FastAPI, and
visualizes insights in Streamlit. A retrieval-augmented briefing layer adds
ReliefWeb/GDACS context retrieval and optional local LLM draft generation via
Ollama. Future phases may add ML shortage-risk prediction.

## Data Flow

```
ReliefWeb API ──┐
                ├──> Ingestion ──> Raw Storage ──> Cleaning ──> PostgreSQL
GDACS RSS    ───┘                                              │
                                                               ├──> Mismatch scoring
                                                               ├──> Transfer recommendation engine
                                                               ├──> FastAPI
                                                               ├──> Hybrid RAG + optional Ollama LLM
                                                               └──> Streamlit dashboard
                                                                    (situation report + operational map)
```

End-to-end pipeline:

```
ReliefWeb/GDACS ingestion
  → PostgreSQL storage
  → mismatch scoring
  → transfer recommendation engine
  → hybrid RAG retrieval with pgvector
  → optional local Ollama AI briefing
  → dashboard situation report and operational map
```

## RAG Pipeline

```
ReliefWeb/GDACS crisis records
  → corpus building (rag/build_corpus.py)
  → document chunking (rag/chunk_documents.py)
  → Ollama nomic-embed-text embeddings (rag/embed_chunks.py)
  → PostgreSQL pgvector vector storage (database/create_rag_tables.py)
  → hybrid semantic + keyword retrieval (rag/hybrid_retriever.py)
  → metadata boosting by country / event / source
  → fallback labeling (is_fallback)
  → local LLM briefing generation with Ollama llama3.2 (rag/llm_briefing.py)
```

### Retrieval scoring

Hybrid retrieval combines:

- **Semantic similarity** — pgvector cosine search over 768-dim embeddings
- **Keyword scoring** — scikit-learn TF-IDF over chunk text
- **Metadata boost** — country, event type, and source alignment with the zone query

Country-specific results are preferred. If too few country-specific chunks match,
fallback (general) results are included and labeled `is_fallback: true` so downstream
UI and prompts can treat them as supporting—not direct—country evidence.

## Local LLM Generation

AI-assisted operational briefings are generated locally using Ollama `llama3.2`.

| Principle | Behavior |
|-----------|----------|
| Primary event | The zone's related GDACS disaster alert |
| Retrieved context | Supporting evidence only; does not replace the primary alert |
| Fact grounding | Prompt instructs the model not to invent facts |
| Dashboard label | Output shown as an AI-assisted draft requiring review |
| Default brief | Template-based operational brief remains the stable default |

The AI endpoint (`GET /reports/ai-zone-briefing/{zone_id}`) is optional and
on-demand. It does not replace template briefs, PDF export, or copy actions.

## Transfer Recommendation Engine

`analytics/reallocation_engine.py` matches shortage zones to surplus zones by
resource type using mismatch score outputs.

| Behavior | Detail |
|----------|--------|
| Input | Mismatch rows with shortage and surplus status labels |
| Prioritization | Same-country transfer candidates first |
| Fallback | Cross-country candidates labeled lower-confidence |
| Output fields | Quantity, from/to zones, confidence, match type, feasibility note |
| Validation | Recommendations require field coordinator review |

**API:** `GET /mismatches/reallocation-recommendations`

Recommendations are generated from simulated inventory and request data. They
support coordination planning but are not dispatch orders.

## Overall Situation Report

`GET /reports/situation-report` returns a deterministic, template-based report
across all zones. It is **not LLM-generated**.

The report combines:

- mismatch scores and resource gaps
- surplus summaries
- transfer recommendation logic
- template-generated operational interpretation, recommended actions, and limitations

The Streamlit **Situation Overview** tab fetches this report on demand via
**Generate Situation Report**. Operational Snapshot KPIs remain the primary
dashboard metrics; the report section focuses on interpretation and detail.

## API Layers

| Layer | Role |
|-------|------|
| `/crises` | ReliefWeb reports and GDACS alerts |
| `/resources` | Zones, organizations, inventory, requests |
| `/mismatches` | Shortage/surplus analytics and reallocation recommendations |
| `/reports/overview` | System KPIs |
| `/reports/situation-report` | Deterministic overall situation report |
| `/reports/zone-briefing/{zone_id}` | Template operational brief (structured JSON) |
| `/reports/rag-zone-context/{zone_id}` | Hybrid-retrieved ReliefWeb/GDACS context |
| `/reports/ai-zone-briefing/{zone_id}` | Local LLM-assisted draft briefing |

## Dashboard

### Situation Overview

- Operational Snapshot KPI cards
- On-demand **Overall Situation Report** (template-based)
- Workflow, data sources, and priority score explanation

### Operational Map

- Zone selection via map marker or dropdown
- Template operational briefing (default, deterministic)
- Retrieved crisis context (after viewing template brief)
- Optional **Generate AI-Assisted Brief** button
- **Recommended Resource Transfers** for selected destination zones
- PDF download and copy brief actions
- Data transparency note (public vs simulated sources)

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI |
| Dashboard | Streamlit |
| Database | PostgreSQL |
| Vector search | pgvector |
| Embeddings | Ollama `nomic-embed-text` |
| Generation | Ollama `llama3.2` |
| Keyword scoring | scikit-learn / TF-IDF |
| Charts / map | Plotly |
| Local infra | Docker Compose |

## Limitations

- Operational inventory and resource request data are **simulated prototype data**
- Public humanitarian records are limited to ReliefWeb and GDACS coverage
- **Transfer recommendations must be validated by field coordinators** before dispatch
- **Cross-country fallback transfers** require customs, logistics, and partner review
- AI-assisted briefings are **drafts** requiring human review
- This is a **portfolio prototype**, not a production emergency response system
- The system does not make final operational decisions

## Status

- Week 1–5 — ingestion, PostgreSQL, mismatch analytics, FastAPI, Streamlit dashboard
- Week 6 Part 1 — template zone operational briefs on Operational Map
- Week 6 Part 2 — RAG corpus, pgvector embeddings, hybrid retrieval, local LLM briefings
- Portfolio extensions — resource reallocation recommendations, Overall Situation Report
