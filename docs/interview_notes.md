# Interview Notes

> Space for talking points about the Crisis Resource Intelligence Network project:
> problem framing, technical decisions, trade-offs, and demo walkthroughs.

## Key Talking Points

- **Problem**: Humanitarian organizations struggle to match resource supply with crisis-driven demand in real time.
- **Approach**: Ingest public crisis data, normalize it, compute mismatches, and surface actionable intelligence.
- **Differentiators**: End-to-end pipeline from raw APIs to dashboard, with planned ML and RAG layers.

## Why simulated resource data?

Real NGO inventory and medical supply data is usually not public for privacy, security, and operational reasons. I simulated this part of the system to prototype the schema and analytics workflow while using real public data for disaster alerts and humanitarian reports.

## Mismatch engine explanation

The mismatch engine compares available supply and requested demand by zone/resource type. It calculates a shortage gap, shortage ratio, and urgency-weighted mismatch score. This creates an interpretable analytics layer before adding machine learning, which is important because humanitarian coordinators need transparent reasoning, not just black-box predictions.

## Backend explanation

I used FastAPI to expose the PostgreSQL-backed analytics layer through REST endpoints. This separates data storage and analysis from the user interface, allowing the same backend to support a dashboard, prompt-based AI reports, a natural-language assistant, or external integrations later.

## Dashboard explanation

I built a Streamlit dashboard on top of the FastAPI backend instead of connecting directly to the database. This makes the architecture cleaner because the dashboard consumes the same REST endpoints that a future frontend, AI reporting layer, or external user could consume.

## Zone briefing endpoint explanation

Before adding AI-generated reports, I created a structured briefing endpoint that gathers all relevant data for a selected zone. This keeps the AI layer grounded in deterministic database outputs instead of relying on unstructured generation alone.

## AI reports explanation

I first implemented template-based AI reports before adding an external LLM. This allowed me to design the reporting workflow and ensure the generated briefings are grounded in deterministic database outputs. A future RAG layer can enrich the reports with retrieved ReliefWeb and GDACS context.

## Operational briefing explanation

I embedded the reporting workflow inside the Priority Needs page instead of making it a separate chatbot-style feature. This keeps the reporting tied to actual shortage decisions. The current version is template-based and grounded in database outputs; a future RAG layer can add richer document context from ReliefWeb and GDACS.

## Map-based briefing explanation

I moved reports into the Operational Map so briefings are generated in context. A user selects a zone on the map, reviews priority needs and related disaster information, then views or exports a Zone Operational Brief. The current version is template-based and grounded in PostgreSQL outputs; future RAG can enrich the narrative with retrieved ReliefWeb and GDACS text.

The report workflow is map-centered. Users first identify a crisis zone on the operational map, then view or export a zone brief from the selected-zone panel. The report is generated from structured database outputs, which keeps it explainable and avoids ungrounded AI generation before the RAG layer is added.
