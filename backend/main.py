"""
FastAPI application entry point.

Exposes a minimal health-check API for the Crisis Resource Intelligence Network.
Additional routes for crises, resources, mismatches, and reports will be added
as the database and analytics layers are built.

Run: uvicorn backend.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Crisis Resource Intelligence Network",
    description="API for humanitarian crisis data, resource tracking, and supply-demand analysis.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    """Root endpoint with project info."""
    return {
        "project": "Crisis Resource Intelligence Network",
        "status": "Week 1 setup",
        "docs": "/docs",
    }


@app.get("/health")
def health_check() -> dict:
    """Health check endpoint for local development and monitoring."""
    return {"status": "ok"}
