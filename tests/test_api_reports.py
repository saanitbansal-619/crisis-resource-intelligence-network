"""DB-backed API tests for reports and optimized transfers.

Every test skips gracefully when PostgreSQL or sample data is unavailable.
No live calls to ReliefWeb, GDACS, Ollama, or deployed URLs are made.
"""

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from conftest import database_available  # noqa: E402

try:
    from backend.main import app

    _IMPORT_ERROR = None
except SystemExit as exc:
    app = None
    _IMPORT_ERROR = f"backend.main could not be imported (no DATABASE_URL config): {exc}"
except Exception as exc:  # pragma: no cover - defensive
    app = None
    _IMPORT_ERROR = f"backend.main import failed: {exc}"

OVERVIEW_KEYS = {
    "total_zones",
    "total_organizations",
    "total_inventory_records",
    "total_request_records",
    "total_mismatch_records",
}

OPTIMIZED_TRANSFER_KEYS = {
    "optimization_status",
    "total_quantity_moved",
    "total_simulated_transport_cost",
    "recommendations",
}


@pytest.fixture(scope="module")
def client() -> TestClient:
    if app is None:
        pytest.skip(_IMPORT_ERROR or "FastAPI app unavailable")
    if not database_available():
        pytest.skip("PostgreSQL is not available; DB-backed report tests skipped.")
    return TestClient(app)


def test_overview_returns_expected_keys(client: TestClient) -> None:
    response = client.get("/reports/overview")
    assert response.status_code == 200

    body = response.json()
    missing = OVERVIEW_KEYS - set(body)
    assert not missing, f"Missing overview keys: {missing}"


def test_overview_counts_are_non_negative_integers(client: TestClient) -> None:
    body = client.get("/reports/overview").json()
    for key in OVERVIEW_KEYS:
        value = body.get(key)
        assert isinstance(value, int), f"{key} should be an integer"
        assert value >= 0, f"{key} should be non-negative"


def test_optimized_transfers_returns_expected_keys(client: TestClient) -> None:
    response = client.get("/mismatches/optimized-transfers")
    assert response.status_code == 200

    body = response.json()
    missing = OPTIMIZED_TRANSFER_KEYS - set(body)
    assert not missing, f"Missing optimized-transfer keys: {missing}"


def test_optimized_transfers_payload_shapes(client: TestClient) -> None:
    body = client.get("/mismatches/optimized-transfers").json()
    assert isinstance(body.get("optimization_status"), str)
    assert isinstance(body.get("recommendations"), list)
    assert body.get("total_quantity_moved", 0) >= 0
    assert body.get("total_simulated_transport_cost", 0) >= 0
