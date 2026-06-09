"""
FastAPI application entry point.

Exposes crisis data, resource coordination, and mismatch analytics via REST.

Run: uvicorn backend.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.database import check_database_connection
from backend.routes import crises, mismatches, reports, resources

app = FastAPI(
    title="Crisis Resource Intelligence Network API",
    description=(
        "API for crisis monitoring, humanitarian resource coordination, "
        "and supply-demand mismatch analytics."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crises.router)
app.include_router(resources.router)
app.include_router(mismatches.router)
app.include_router(reports.router)


@app.get("/")
def root() -> dict:
    """API root with basic status information."""
    return {
        "message": "Crisis Resource Intelligence Network API",
        "status": "running",
        "docs_url": "/docs",
    }


@app.get("/health")
def health_check():
    """Health check with database connectivity status."""
    if check_database_connection():
        return {
            "api_status": "healthy",
            "database_status": "connected",
        }

    return JSONResponse(
        status_code=503,
        content={
            "api_status": "healthy",
            "database_status": "disconnected",
            "detail": "Could not connect to PostgreSQL. Confirm Docker is running and DATABASE_URL is correct.",
        },
    )
