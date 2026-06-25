"""API root and health endpoint tests using FastAPI TestClient.

These tests do not require external APIs, Render services, or Ollama.
DB-backed checks skip gracefully when PostgreSQL is unavailable.
"""

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from conftest import database_available  # noqa: E402

try:
    from backend.main import app

    _IMPORT_ERROR = None
except SystemExit as exc:  # backend.database exits if DATABASE_URL is missing
    app = None
    _IMPORT_ERROR = f"backend.main could not be imported (no DATABASE_URL config): {exc}"
except Exception as exc:  # pragma: no cover - defensive
    app = None
    _IMPORT_ERROR = f"backend.main import failed: {exc}"


@pytest.fixture(scope="module")
def client() -> TestClient:
    if app is None:
        pytest.skip(_IMPORT_ERROR or "FastAPI app unavailable")
    return TestClient(app)


def test_root_returns_200(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200


def test_root_contains_expected_message(client: TestClient) -> None:
    body = client.get("/").json()
    assert body.get("message") == "Crisis Resource Intelligence Network API"


def test_root_status_running(client: TestClient) -> None:
    body = client.get("/").json()
    assert body.get("status") == "running"


def test_health_returns_valid_json(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code in (200, 503)

    body = response.json()
    assert "api_status" in body
    assert "database_status" in body

    if response.status_code == 200:
        assert body["database_status"] == "connected"
    else:
        assert body["database_status"] == "disconnected"


def test_health_database_status_consistent(client: TestClient) -> None:
    body = client.get("/health").json()
    if database_available():
        assert body["database_status"] == "connected"
    else:
        pytest.skip("PostgreSQL is not available; database status check skipped.")
