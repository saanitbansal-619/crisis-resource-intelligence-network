# Architecture

> Living document describing the Crisis Resource Intelligence Network system design.

## Overview

The platform ingests public humanitarian crisis data, stores and normalizes it in
PostgreSQL, computes supply-demand mismatches, exposes results via FastAPI, and
visualizes insights in Streamlit. A retrieval-augmented briefing layer adds
ReliefWeb/GDACS context retrieval and optional local LLM draft generation via
Ollama. Future phases may add ML shortage-risk prediction.

## Data Flow

```
ReliefWeb API ──┐
                ├──> Ingestion ──> Raw Storage ──> Cleaning ──> PostgreSQL
GDACS RSS    ───┘                                              │
                                                               ├──> Mismatch Analytics
                                                               ├──> FastAPI
                                                               ├──> Streamlit Dashboard
                                                               └──> RAG + Local LLM Briefing
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

## API Layers

| Layer | Role |
|-------|------|
| `/crises` | ReliefWeb reports and GDACS alerts |
| `/resources` | Zones, organizations, inventory, requests |
| `/mismatches` | Shortage/surplus analytics |
| `/reports/zone-briefing/{zone_id}` | Template operational brief (structured JSON) |
| `/reports/rag-zone-context/{zone_id}` | Hybrid-retrieved ReliefWeb/GDACS context |
| `/reports/ai-zone-briefing/{zone_id}` | Local LLM-assisted draft briefing |

## Dashboard (Operational Map)

- Zone selection via map marker or dropdown
- Template operational briefing (default, deterministic)
- Retrieved crisis context (after viewing template brief)
- Optional **Generate AI-Assisted Brief** button
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
- AI-generated briefings are **drafts** requiring human review
- This is a **portfolio prototype**, not a production deployment
- The system does not make final operational decisions

## Status

- Week 1–5 — ingestion, PostgreSQL, mismatch analytics, FastAPI, Streamlit dashboard
- Week 6 Part 1 — template zone operational briefs on Operational Map
- Week 6 Part 2 — RAG corpus, pgvector embeddings, hybrid retrieval, local LLM briefings
