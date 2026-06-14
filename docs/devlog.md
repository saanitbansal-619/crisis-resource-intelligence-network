# Dev Log

## Week 1 — Project Setup

- Created project skeleton with ingestion, database, analytics, backend, dashboard, ML, and RAG modules.
- Added runnable starter scripts for ReliefWeb and GDACS ingestion.
- Added FastAPI health-check API and Streamlit starter dashboard.
- Configured local PostgreSQL via docker-compose (not yet wired to application code).

## ReliefWeb API Ingestion

Implemented the first working ingestion pipeline using the ReliefWeb API. The script loads an approved appname from a local `.env` file, calls the ReliefWeb reports endpoint, saves raw JSON responses locally, and converts report metadata into a pandas DataFrame for inspection.

Key fields extracted:
- report ID
- title
- countries
- publication date
- source organization
- ReliefWeb URL

This validates the first real external data source for the Crisis Resource Intelligence Network.

## GDACS API Ingestion

Implemented the second working external data source using GDACS disaster alerts. The script fetches active/recent disaster alerts, saves the raw response locally, and converts alert metadata into a pandas DataFrame for inspection.

Key fields extracted:
- alert title
- GDACS report link
- publication date
- disaster description

This gives the project a real-time disaster alert feed that can later be combined with ReliefWeb humanitarian reports for crisis monitoring and resource mismatch analysis.

## Week 2: Data Cleaning and Normalization

Started transforming raw ReliefWeb and GDACS API responses into structured processed CSV files. The cleaning scripts extract key crisis/report metadata, standardize dates, handle nested JSON fields, and prepare the data for PostgreSQL loading.

## Week 2: PostgreSQL Database Setup

Created a local PostgreSQL database with Docker Compose and added schema/loading scripts to move cleaned ReliefWeb and GDACS data into structured tables. The database layer allows the project to move beyond CSV files and support SQL-based analytics, FastAPI endpoints, and later dashboard queries.

## Week 3: Simulated Humanitarian Resource Data

Added simulated operational data for humanitarian organizations, crisis zones, resource inventory, and resource requests. This creates the supply and demand layer of the system, allowing the project to move from crisis monitoring into resource coordination analysis. The data is simulated because real-time NGO inventory data is not publicly available, but the schema is designed to reflect realistic field reporting workflows.

## Week 3: Supply-Demand Mismatch Engine

Built the first analytics engine for the crisis resource system. The mismatch engine aggregates simulated resource inventory and requests by zone and resource type, calculates shortage gaps, shortage ratios, urgency-weighted mismatch scores, and assigns operational status labels such as surplus, stable, severe shortage, and critical shortage. Results are stored in PostgreSQL for downstream API, dashboard, and ML use.

## Week 4: FastAPI Backend

Added a FastAPI backend that exposes crisis reports, GDACS alerts, simulated humanitarian resource data, mismatch scores, and summary KPIs from PostgreSQL. This separates the analytics/database layer from future dashboard and AI-reporting layers, making the system easier to test, extend, and deploy.

## Week 5: Streamlit Operations Dashboard

Added a Streamlit dashboard that consumes the FastAPI backend and visualizes crisis resource intelligence metrics. The dashboard includes overview KPIs, critical shortages, surplus resources, resource summaries, and a crisis map. The design uses a serious humanitarian operations style to support professional demos and decision-support workflows.

Polished the dashboard UI with compact header spacing, human-readable table labels, resource-type formatting, tab-level KPI cards, improved chart axis labels, and a focused crisis map view centered on active demo regions.

Redesigned the dashboard with a humanitarian operations visual style for NGO and stakeholder presentation: warm off-white background, white cards, deep humanitarian blue accents, muted severity colors, field-coordination navigation labels, and accessible non-technical language throughout the UI.

Polished the Situation Overview page for stakeholder demos by removing technical backend/API controls from the main UI and adding About, How It Works, Data Sources, pipeline, and priority score explanatory sections.

## Week 6: Zone Briefing Endpoint

Added a zone briefing endpoint that consolidates zone metadata, priority needs, surplus resources, inventory, requests, and related disaster alerts into one structured response. This endpoint prepares the system for prompt-based AI situation reports and operational recommendations.

## Week 6: Template-Based AI Reports

Added a dashboard report generator that creates structured operational briefings from the zone briefing endpoint. Reports are currently template-based and deterministic, using PostgreSQL-backed shortage, inventory, request, and disaster alert data. This prepares the system for a future RAG/LLM layer while keeping outputs grounded and explainable.

## Week 6: Operational Briefing Workflow

Moved the report generator into the Priority Needs workflow as an embedded Operational Briefing section. Briefings are generated from the zone briefing endpoint and remain template-based for now, preparing the system for a future RAG layer without introducing ungrounded AI output.

## Week 6: Map-Based Zone Operational Briefs

Moved the briefing workflow into the Operational Map. Users can select a crisis zone, review zone-level details, view a formatted Zone Operational Brief in the dashboard, and optionally export the brief as a PDF. The briefing is template-based and grounded in the zone briefing endpoint, preparing the system for a future RAG-enhanced reporting layer.

## Week 6: In-App Zone Brief Preview and PDF Export

Improved the Operational Map briefing workflow so selecting a zone shows a compact action panel. Users can view a formatted Zone Operational Brief directly in the dashboard, optionally download it as a PDF, or open copy-ready text. PDF export uses ReportLab and the dashboard handles missing dependencies gracefully.

## Week 6 Part 2: RAG Corpus and TF-IDF Baseline

Added the first retrieval layer in `rag/`. ReliefWeb and GDACS records from PostgreSQL are exported to a local corpus, split into searchable chunks, and indexed with a TF-IDF keyword retriever. This established the offline retrieval baseline before semantic search.

## Week 6 Part 2: pgvector Semantic Retrieval

Enabled pgvector in Docker Compose (`pgvector/pgvector:0.8.1-pg15`). Added embedding tables and a script to embed chunks locally with Ollama `nomic-embed-text` (768 dimensions). Semantic retrieval runs over PostgreSQL vector storage.

## Week 6 Part 2: Hybrid Retrieval and RAG API

Combined semantic similarity, TF-IDF keyword scoring, and metadata boosting (country, event type, source) into a hybrid retriever. Country-specific results are preferred; fallback results are labeled when country-specific coverage is thin. Exposed zone-level retrieved context via `GET /reports/rag-zone-context/{zone_id}` and integrated it into the Operational Map dashboard.

## Week 6 Part 2: Local LLM-Assisted Briefings

Added optional AI-assisted operational brief generation using Ollama `llama3.2`. The prompt grounds output in structured zone metrics and retrieved ReliefWeb/GDACS context, with the related disaster alert as the primary event and retrieved sources as supporting context only. The dashboard labels output as an AI-assisted draft requiring review. Template-based briefs remain the stable default.
