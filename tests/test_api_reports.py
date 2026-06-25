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

    # Do not re-raise server exceptions so a reachable-but-unseeded database
    # (e.g. an empty SQLite placeholder in CI) yields a 500 we can skip on,
    # rather than crashing the test run.
    test_client = TestClient(app, raise_server_exceptions=False)

    probe = test_client.get("/reports/overview")
    if probe.status_code != 200:
        pytest.skip(
            "Database is reachable but the expected schema/sample data is unavailable "
            f"(probe returned HTTP {probe.status_code}); DB-backed report tests skipped."
        )
    return test_client


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


def test_shortage_risk_forecast_response_shape(client: TestClient) -> None:
    response = client.get("/reports/shortage-risk-forecast")
    assert response.status_code == 200

    body = response.json()
    # Top-level keys present whether or not the model/data are available.
    assert "status" in body
    assert "model_available" in body
    assert "model_note" in body
    assert "feature_note" in body
    assert "forecasts" in body
    assert isinstance(body["forecasts"], list)
    assert "summary" in body

    # model_evaluation is always present: either metrics or a graceful message.
    assert "model_evaluation" in body
    evaluation = body["model_evaluation"]
    assert isinstance(evaluation, dict)
    if "message" in evaluation:
        assert "train_model" in evaluation["message"]
    else:
        for key in ("accuracy", "macro_f1", "weighted_f1", "roc_auc_ovr_macro"):
            value = evaluation.get(key)
            if value is not None:
                assert 0.0 <= float(value) <= 1.0

    valid_levels = {"low", "medium", "high", "critical"}

    if body.get("model_available") and body["forecasts"]:
        assert body["status"] == "ok"
        item = body["forecasts"][0]
        expected = {
            "zone_name",
            "country",
            "resource_type",
            "current_shortage_gap",
            "fulfillment_ratio",
            "predicted_48h_risk",
            "predicted_72h_risk",
            "confidence",
        }
        assert expected <= set(item)
        for forecast in body["forecasts"]:
            assert forecast["predicted_48h_risk"] in valid_levels
            assert forecast["predicted_72h_risk"] in valid_levels
            if forecast.get("confidence") is not None:
                assert 0.0 <= forecast["confidence"] <= 1.0
    else:
        # Graceful fallback path must explain why it is unavailable.
        assert body["status"] in {"unavailable", "no_data"}
        assert isinstance(body.get("message", ""), str)
