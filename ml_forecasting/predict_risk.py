"""
Shortage-risk prediction using the trained baseline model.

Loads the persisted model bundle and produces 48-72 hour shortage severity risk
predictions. This is a prototype forecasting aid trained on simulated/proxy
labels; it supports early planning and is not an automated decision-maker.

Run: python -m ml_forecasting.predict_risk
"""

from __future__ import annotations

from pathlib import Path

from ml_forecasting.feature_builder import (
    FEATURE_COLUMNS,
    RISK_LEVELS,
    build_feature_frame,
)
from ml_forecasting.train_model import METRICS_PATH, MODEL_PATH

METRICS_UNAVAILABLE_MESSAGE = (
    "Model evaluation metrics unavailable. Run python -m ml_forecasting.train_model "
    "to generate metrics."
)

METHOD_NOTE = (
    "Prototype shortage-risk model trained on simulated/proxy operational labels "
    "derived from shortage severity, fulfillment ratio, and urgency assumptions. "
    "It estimates 48-72 hour shortage severity to support early planning and "
    "complements (does not replace) the OR-Tools optimization plan or human judgment."
)


class ModelUnavailableError(RuntimeError):
    """Raised when the trained model file cannot be loaded."""


def load_model(model_path: Path | str = MODEL_PATH) -> dict:
    """Load the persisted model bundle, raising ModelUnavailableError if missing."""
    import joblib

    path = Path(model_path)
    if not path.exists():
        raise ModelUnavailableError(
            f"Shortage-risk model not found at {path}. "
            "Train it with: python -m ml_forecasting.train_model"
        )
    try:
        bundle = joblib.load(path)
    except Exception as exc:  # pragma: no cover - corrupt/incompatible artifact
        raise ModelUnavailableError(f"Failed to load shortage-risk model: {exc}") from exc

    if not isinstance(bundle, dict) or "pipeline" not in bundle:
        raise ModelUnavailableError("Shortage-risk model artifact is invalid.")
    return bundle


def load_model_evaluation(metrics_path: Path | str = METRICS_PATH) -> dict | None:
    """Load a compact model-evaluation summary from the metrics JSON.

    Returns None when the metrics file is missing or unreadable so callers can
    show a graceful message instead of failing.
    """
    import json

    path = Path(metrics_path)
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:  # pragma: no cover - corrupt artifact
        return None

    summary = {
        "model_type": data.get("model_type"),
        "label_type": data.get("label_type"),
        "test_size": data.get("test_size"),
        "n_test_samples": data.get("n_test_samples"),
        "accuracy": data.get("accuracy"),
        "macro_precision": data.get("macro_precision"),
        "macro_recall": data.get("macro_recall"),
        "macro_f1": data.get("macro_f1"),
        "weighted_f1": data.get("weighted_f1"),
        "roc_auc_ovr_macro": data.get("roc_auc_ovr_macro"),
        "evaluation_note": data.get("evaluation_note"),
    }
    if data.get("roc_auc_note"):
        summary["roc_auc_note"] = data["roc_auc_note"]
    return summary


def escalate_risk_level(level: str) -> str:
    """Return the next-higher risk level (capped at 'critical')."""
    try:
        index = RISK_LEVELS.index(level)
    except ValueError:
        return level
    return RISK_LEVELS[min(index + 1, len(RISK_LEVELS) - 1)]


def _project_horizons(
    base_level: str,
    shortage_gap: int,
    fulfillment_ratio: float,
    urgency_score: int,
    mismatch_score: float,
) -> tuple[str, str]:
    """48h risk is the model prediction; 72h escalates under sustained pressure.

    The 72-hour projection is a transparent persistence heuristic (not a second
    trained model): if a shortage is ongoing and either under-fulfilled or under
    high urgency/mismatch pressure, risk is escalated one level to reflect
    continued unmet demand.
    """
    risk_48h = base_level
    high_pressure = urgency_score >= 3 or mismatch_score >= 500.0
    if shortage_gap > 0 and (fulfillment_ratio < 0.75 or high_pressure):
        risk_72h = escalate_risk_level(base_level)
    else:
        risk_72h = base_level
    return risk_48h, risk_72h


def predict_shortage_risk(
    records: list[dict],
    model_bundle: dict | None = None,
    model_path: Path | str = MODEL_PATH,
) -> list[dict]:
    """Predict shortage risk for raw zone/resource records.

    Each result includes the predicted risk level, 48h/72h horizon risk,
    fulfillment ratio, confidence (max class probability), global top
    contributing features, and a method note. Raises ModelUnavailableError if
    the model cannot be loaded.
    """
    if not records:
        return []

    bundle = model_bundle or load_model(model_path)
    pipeline = bundle["pipeline"]
    label_encoder = bundle.get("label_encoder")
    top_features = bundle.get("top_features", [])

    feature_frame = build_feature_frame(records, include_label=False)
    features = feature_frame[FEATURE_COLUMNS]

    raw_predictions = pipeline.predict(features)
    if label_encoder is not None:
        predicted_levels = [str(level) for level in label_encoder.inverse_transform(raw_predictions)]
    else:
        predicted_levels = [str(level) for level in raw_predictions]

    try:
        probabilities = pipeline.predict_proba(features)
    except Exception:  # pragma: no cover - classifier without proba
        probabilities = None

    results: list[dict] = []
    for index, (_, feature_row) in enumerate(feature_frame.iterrows()):
        base_level = predicted_levels[index]

        if probabilities is not None:
            confidence = round(float(max(probabilities[index])), 4)
        else:
            confidence = None

        shortage_gap = int(feature_row["shortage_gap"])
        fulfillment_ratio = float(feature_row["fulfillment_ratio"])
        urgency_score = int(feature_row["urgency_score"])
        mismatch_score = float(feature_row["mismatch_score"])
        risk_48h, risk_72h = _project_horizons(
            base_level, shortage_gap, fulfillment_ratio, urgency_score, mismatch_score
        )

        results.append(
            {
                "zone_id": feature_row.get("zone_id", ""),
                "zone_name": feature_row.get("zone_name", "Unknown Zone"),
                "country": feature_row["country"],
                "resource_type": feature_row["resource_type"],
                "current_shortage_gap": shortage_gap,
                "fulfillment_ratio": round(fulfillment_ratio, 4),
                "predicted_risk_level": base_level,
                "predicted_48h_risk": risk_48h,
                "predicted_72h_risk": risk_72h,
                "risk_probability": confidence,
                "confidence": confidence,
                "top_features": list(top_features),
                "model_note": METHOD_NOTE,
                "method_note": METHOD_NOTE,
            }
        )
    return results


def main() -> None:
    from ml_forecasting.feature_builder import load_feature_records_from_db

    try:
        records = load_feature_records_from_db()
    except Exception as exc:
        print(f"Could not load feature records: {exc}")
        return

    try:
        predictions = predict_shortage_risk(records)
    except ModelUnavailableError as exc:
        print(str(exc))
        return

    print(f"Forecasts: {len(predictions)}")
    for item in sorted(
        predictions,
        key=lambda r: RISK_LEVELS.index(r["predicted_48h_risk"]) if r["predicted_48h_risk"] in RISK_LEVELS else 0,
        reverse=True,
    )[:10]:
        print(
            f"{item['zone_name']} / {item['resource_type']}: "
            f"48h={item['predicted_48h_risk']} 72h={item['predicted_72h_risk']} "
            f"conf={item['confidence']} gap={item['current_shortage_gap']} "
            f"fill={item['fulfillment_ratio']}"
        )
    print(f"\n{METHOD_NOTE}")


if __name__ == "__main__":
    main()
