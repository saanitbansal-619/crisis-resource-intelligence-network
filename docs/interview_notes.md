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
