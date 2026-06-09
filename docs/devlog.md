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
