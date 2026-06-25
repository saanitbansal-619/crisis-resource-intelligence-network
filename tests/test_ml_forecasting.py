"""Tests for the shortage-risk ML forecasting layer.

Feature engineering and proxy-label logic are pure functions, so they run
without a database. Model-dependent tests train a tiny in-memory model so they
do not require the persisted artifact or live data. No external services
(ReliefWeb, GDACS, Render, Ollama) are contacted.
"""

import pytest

from ml_forecasting.feature_builder import (
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    RISK_LEVELS,
    assign_proxy_risk_level,
    build_feature_frame,
    build_raw_records,
    compute_fulfillment_ratio,
    is_critical_resource,
    urgency_to_score,
)


def _raw_row(**overrides) -> dict:
    base = {
        "zone_id": "Z1",
        "zone_name": "Test Zone",
        "country": "CountryA",
        "resource_type": "blankets",
        "crisis_type": "flood",
        "available_quantity": 100,
        "request_quantity": 500,
        "shortage_gap": 400,
        "urgency_level": "high",
        "mismatch_score": 800.0,
        "gdacs_alert_count": 5,
        "report_count": 3,
    }
    base.update(overrides)
    return base


# --- Feature-builder output schema -------------------------------------------


def test_build_raw_records_normalizes_types_and_defaults() -> None:
    records = build_raw_records([{"zone_name": "Z", "shortage_gap": "300", "mismatch_score": "12.5"}])
    assert len(records) == 1
    record = records[0]
    assert record["shortage_gap"] == 300
    assert record["mismatch_score"] == 12.5
    assert record["country"] == "unknown"  # missing -> safe default
    assert record["crisis_type"] == "unknown"


def test_build_feature_frame_has_all_feature_columns_and_label() -> None:
    frame = build_feature_frame([_raw_row()], include_label=True)
    for column in FEATURE_COLUMNS:
        assert column in frame.columns
    assert LABEL_COLUMN in frame.columns


def test_build_feature_frame_without_label() -> None:
    frame = build_feature_frame([_raw_row()], include_label=False)
    assert LABEL_COLUMN not in frame.columns
    assert "fulfillment_ratio" in frame.columns


def test_fulfillment_ratio_bounds() -> None:
    assert compute_fulfillment_ratio(0, 100) == 0.0
    assert compute_fulfillment_ratio(50, 100) == 0.5
    assert compute_fulfillment_ratio(500, 100) == 1.0  # clamped
    assert compute_fulfillment_ratio(10, 0) == 1.0  # no demand -> met


def test_urgency_to_score_mapping() -> None:
    assert urgency_to_score("low") == 1
    assert urgency_to_score("critical") == 4
    assert urgency_to_score(None) == 1


# --- Proxy label generation ---------------------------------------------------


def test_proxy_label_low_when_no_shortage() -> None:
    assert assign_proxy_risk_level(0, 1.0, 4, 5000) == "low"
    assert assign_proxy_risk_level(-100, 1.0, 4, 5000) == "low"


def test_proxy_label_critical_for_severe_unmet_urgent_shortage() -> None:
    assert assign_proxy_risk_level(2000, 0.1, 4, 5000) == "critical"


def test_proxy_label_thresholds_follow_fulfillment_ratio() -> None:
    # Low pressure, non-critical resource: bands fall back to ratio thresholds.
    assert assign_proxy_risk_level(400, 0.40, 1, 0, resource_type="blankets") == "high"
    assert assign_proxy_risk_level(400, 0.70, 1, 0, resource_type="blankets") == "medium"
    assert assign_proxy_risk_level(400, 0.90, 1, 0, resource_type="blankets") == "low"


def test_proxy_label_resource_criticality_escalates() -> None:
    assert is_critical_resource("insulin")
    assert not is_critical_resource("blankets")
    # Very low fulfillment of a life-critical resource -> critical even at low mismatch.
    assert assign_proxy_risk_level(400, 0.10, 1, 0, resource_type="insulin") == "critical"


def test_proxy_label_is_always_a_known_level() -> None:
    for gap in (-50, 50, 500, 5000):
        for ratio in (0.0, 0.3, 0.6, 0.9, 1.0):
            level = assign_proxy_risk_level(gap, ratio, 2, 400, resource_type="water_kits")
            assert level in RISK_LEVELS


def test_proxy_label_monotonic_severity() -> None:
    mild = assign_proxy_risk_level(50, 0.9, 1, 50)
    severe = assign_proxy_risk_level(3000, 0.05, 4, 5000)
    assert RISK_LEVELS.index(severe) >= RISK_LEVELS.index(mild)


# --- Prediction output schema -------------------------------------------------


@pytest.fixture(scope="module")
def trained_bundle() -> dict:
    """Train a tiny in-memory RandomForest so prediction tests need no artifact/DB."""
    pytest.importorskip("sklearn")
    from ml_forecasting.train_model import _build_pipeline, _random_forest_classifier

    records = [
        _raw_row(shortage_gap=2000, available_quantity=10, request_quantity=2010, urgency_level="critical", mismatch_score=6000, resource_type="insulin"),
        _raw_row(shortage_gap=-100, available_quantity=600, request_quantity=500, urgency_level="low", mismatch_score=0, resource_type="food_kits"),
        _raw_row(shortage_gap=300, available_quantity=200, request_quantity=500, urgency_level="medium", mismatch_score=400, resource_type="blankets"),
        _raw_row(shortage_gap=80, available_quantity=420, request_quantity=500, urgency_level="low", mismatch_score=120, resource_type="hygiene_kits"),
        _raw_row(shortage_gap=1500, available_quantity=50, request_quantity=1550, urgency_level="high", mismatch_score=3000, country="CountryB", resource_type="water_kits"),
        _raw_row(shortage_gap=0, available_quantity=500, request_quantity=500, urgency_level="low", mismatch_score=0, resource_type="medicine"),
    ]
    frame = build_feature_frame(records, include_label=True)
    pipeline = _build_pipeline(_random_forest_classifier())
    pipeline.fit(frame[FEATURE_COLUMNS], frame[LABEL_COLUMN])
    return {
        "pipeline": pipeline,
        "label_encoder": None,
        "feature_columns": FEATURE_COLUMNS,
        "top_features": ["numeric__shortage_gap", "numeric__mismatch_score"],
        "classes": list(pipeline.named_steps["classifier"].classes_),
    }


def test_prediction_output_schema(trained_bundle: dict) -> None:
    from ml_forecasting.predict_risk import predict_shortage_risk

    records = [_raw_row(), _raw_row(shortage_gap=-50, available_quantity=600, request_quantity=500)]
    results = predict_shortage_risk(records, model_bundle=trained_bundle)

    assert len(results) == 2
    required_keys = {
        "zone_name",
        "country",
        "resource_type",
        "current_shortage_gap",
        "fulfillment_ratio",
        "predicted_risk_level",
        "predicted_48h_risk",
        "predicted_72h_risk",
        "confidence",
        "top_features",
        "model_note",
    }
    for item in results:
        assert required_keys <= set(item)


def test_no_prediction_has_invalid_risk_level(trained_bundle: dict) -> None:
    from ml_forecasting.predict_risk import predict_shortage_risk

    records = [
        _raw_row(),
        _raw_row(shortage_gap=5000, available_quantity=0, request_quantity=5000, resource_type="insulin"),
        _raw_row(shortage_gap=-50, available_quantity=600, request_quantity=500),
        _raw_row(shortage_gap=120, available_quantity=400, request_quantity=520, resource_type="tarps"),
    ]
    results = predict_shortage_risk(records, model_bundle=trained_bundle)
    for item in results:
        assert item["predicted_risk_level"] in RISK_LEVELS
        assert item["predicted_48h_risk"] in RISK_LEVELS
        assert item["predicted_72h_risk"] in RISK_LEVELS


def test_confidence_between_zero_and_one_when_available(trained_bundle: dict) -> None:
    from ml_forecasting.predict_risk import predict_shortage_risk

    results = predict_shortage_risk([_raw_row(), _raw_row(resource_type="insulin")], model_bundle=trained_bundle)
    for item in results:
        if item["confidence"] is not None:
            assert 0.0 <= item["confidence"] <= 1.0


def test_prediction_72h_not_lower_than_48h(trained_bundle: dict) -> None:
    from ml_forecasting.predict_risk import predict_shortage_risk

    results = predict_shortage_risk([_raw_row()], model_bundle=trained_bundle)
    item = results[0]
    assert RISK_LEVELS.index(item["predicted_72h_risk"]) >= RISK_LEVELS.index(item["predicted_48h_risk"])


def test_prediction_empty_records_returns_empty(trained_bundle: dict) -> None:
    from ml_forecasting.predict_risk import predict_shortage_risk

    assert predict_shortage_risk([], model_bundle=trained_bundle) == []


# --- Graceful fallback when the model artifact is missing ---------------------


def test_load_model_missing_raises_with_training_hint(tmp_path) -> None:
    from ml_forecasting.predict_risk import ModelUnavailableError, load_model

    missing = tmp_path / "does_not_exist.joblib"
    with pytest.raises(ModelUnavailableError) as excinfo:
        load_model(missing)
    assert "ml_forecasting.train_model" in str(excinfo.value)


def test_predict_with_missing_model_path_raises(tmp_path) -> None:
    from ml_forecasting.predict_risk import ModelUnavailableError, predict_shortage_risk

    with pytest.raises(ModelUnavailableError):
        predict_shortage_risk([_raw_row()], model_path=tmp_path / "missing.joblib")
