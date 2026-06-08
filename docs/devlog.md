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
