# Architecture

> Living document describing the Crisis Resource Intelligence Network system design.

## Overview

The platform ingests public humanitarian crisis data, stores and normalizes it in
PostgreSQL, computes supply-demand mismatches, exposes results via FastAPI, and
visualizes insights in Streamlit. Future phases add ML shortage-risk prediction
and a RAG crisis assistant.

## Planned Data Flow

```
ReliefWeb API ──┐
                ├──> Ingestion ──> Raw Storage ──> Cleaning ──> PostgreSQL
GDACS RSS    ───┘                                              │
                                                               ├──> Analytics (mismatches)
                                                               ├──> FastAPI
                                                               ├──> Streamlit Dashboard
                                                               ├──> ML (future)
                                                               └──> RAG Assistant (future)
```

## Status

Week 1 — project skeleton and starter scripts only.
