"""
Train a baseline shortage-risk classifier, evaluate it, and persist artifacts.

Prefers XGBoost when available and falls back to a scikit-learn
RandomForestClassifier otherwise. Categorical features are one-hot encoded
inside a preprocessing pipeline. The model learns transparent simulated/proxy
labels, so it is a prototype forecasting aid, not a production demand model.

Evaluation metrics are measured against the simulated/proxy labels (a held-out
test split), NOT real NGO ground-truth outcomes.

Run: python -m ml_forecasting.train_model
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ml_forecasting.feature_builder import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    NUMERIC_FEATURES,
    PROXY_LABEL_NOTE,
    RISK_LEVELS,
    build_training_data,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODEL_DIR / "shortage_risk_model.joblib"
METRICS_PATH = MODEL_DIR / "shortage_risk_metrics.json"

TEST_SIZE = 0.25
RANDOM_STATE = 42

LABEL_TYPE = "simulated/proxy operational labels"
EVALUATION_NOTE = (
    "Metrics are measured against simulated/proxy shortage-risk labels derived from "
    "shortage gap, fulfillment ratio, urgency, and mismatch assumptions, not real NGO "
    "ground-truth outcomes."
)


def _build_preprocessor():
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder

    return ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ("numeric", "passthrough", NUMERIC_FEATURES),
        ]
    )


def _xgboost_classifier(num_classes: int):
    """Return an XGBClassifier if xgboost is importable, else None."""
    try:
        from xgboost import XGBClassifier
    except Exception:
        return None

    return XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="multi:softprob",
        num_class=num_classes,
        tree_method="hist",
        random_state=RANDOM_STATE,
        eval_metric="mlogloss",
    )


def _random_forest_classifier():
    from sklearn.ensemble import RandomForestClassifier

    return RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        random_state=RANDOM_STATE,
        class_weight="balanced",
    )


def _build_pipeline(estimator):
    from sklearn.pipeline import Pipeline

    return Pipeline(steps=[("preprocessor", _build_preprocessor()), ("classifier", estimator)])


def _top_feature_importances(pipeline, limit: int = 5) -> list[str]:
    """Return the most important transformed feature names (global importances)."""
    try:
        preprocessor = pipeline.named_steps["preprocessor"]
        classifier = pipeline.named_steps["classifier"]
        feature_names = list(preprocessor.get_feature_names_out())
        importances = list(classifier.feature_importances_)
        ranked = sorted(zip(feature_names, importances), key=lambda pair: pair[1], reverse=True)
        return [name for name, _ in ranked[:limit]]
    except Exception:
        return []


def _ordered_class_labels(labels: pd.Series) -> list[str]:
    """Return present class labels in canonical low->critical order."""
    present = set(str(value) for value in labels.unique())
    ordered = [level for level in RISK_LEVELS if level in present]
    # Include any unexpected labels deterministically at the end.
    ordered += sorted(present - set(ordered))
    return ordered


def _safe_train_test_split(features, labels, test_size: float, random_state: int):
    """Stratified split when class counts allow, else a graceful non-stratified split."""
    from sklearn.model_selection import train_test_split

    try:
        x_train, x_test, y_train, y_test = train_test_split(
            features, labels, test_size=test_size, random_state=random_state, stratify=labels
        )
        return x_train, x_test, y_train, y_test, True
    except ValueError:
        x_train, x_test, y_train, y_test = train_test_split(
            features, labels, test_size=test_size, random_state=random_state
        )
        return x_train, x_test, y_train, y_test, False


def _jsonable(value):
    """Recursively convert numpy types to plain Python types for JSON."""
    try:
        import numpy as np
    except Exception:  # pragma: no cover
        np = None

    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if np is not None:
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return float(value)
        if isinstance(value, np.ndarray):
            return [_jsonable(v) for v in value.tolist()]
    return value


def _round_or_none(value):
    return None if value is None else round(float(value), 4)


def _compute_metrics(
    y_true: list[str],
    y_pred: list[str],
    proba,
    proba_class_order: list[str],
    class_labels: list[str],
) -> dict:
    """Compute classification metrics against proxy labels (graceful ROC-AUC)."""
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    metrics = {
        "accuracy": _round_or_none(accuracy_score(y_true, y_pred)),
        "macro_precision": _round_or_none(
            precision_score(y_true, y_pred, labels=class_labels, average="macro", zero_division=0)
        ),
        "macro_recall": _round_or_none(
            recall_score(y_true, y_pred, labels=class_labels, average="macro", zero_division=0)
        ),
        "macro_f1": _round_or_none(
            f1_score(y_true, y_pred, labels=class_labels, average="macro", zero_division=0)
        ),
        "weighted_f1": _round_or_none(
            f1_score(y_true, y_pred, labels=class_labels, average="weighted", zero_division=0)
        ),
        "classification_report": _jsonable(
            classification_report(
                y_true, y_pred, labels=class_labels, output_dict=True, zero_division=0
            )
        ),
        "confusion_matrix": _jsonable(
            confusion_matrix(y_true, y_pred, labels=class_labels)
        ),
        "class_labels": class_labels,
    }

    roc_auc = None
    roc_auc_note = None
    classes_in_test = set(y_true)
    if proba is None:
        roc_auc_note = "ROC-AUC unavailable: model does not expose class probabilities."
    elif len(proba_class_order) < 2:
        roc_auc_note = "ROC-AUC unavailable: fewer than two classes."
    elif not set(proba_class_order).issubset(classes_in_test) or len(classes_in_test) < len(proba_class_order):
        roc_auc_note = (
            "ROC-AUC unavailable: not all classes are represented in the held-out test split "
            "(class imbalance in the small proxy dataset)."
        )
    else:
        try:
            roc_auc = _round_or_none(
                roc_auc_score(
                    y_true,
                    proba,
                    multi_class="ovr",
                    average="macro",
                    labels=proba_class_order,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive
            roc_auc_note = f"ROC-AUC unavailable: {exc}"

    metrics["roc_auc_ovr_macro"] = roc_auc
    if roc_auc_note:
        metrics["roc_auc_note"] = roc_auc_note
    return metrics


def train_and_save_model(
    training_frame: pd.DataFrame | None = None,
    model_path: Path | str = MODEL_PATH,
    metrics_path: Path | str = METRICS_PATH,
) -> dict:
    """Train + evaluate the classifier, persist the model bundle and metrics JSON."""
    import joblib
    from sklearn.preprocessing import LabelEncoder

    frame = training_frame if training_frame is not None else build_training_data()
    if frame is None or frame.empty:
        raise RuntimeError("No training data available; cannot train shortage-risk model.")
    if len(frame) < 5:
        raise RuntimeError(
            f"Insufficient training data ({len(frame)} rows) to train a stable model."
        )

    features = frame[FEATURE_COLUMNS]
    raw_labels = frame[LABEL_COLUMN].astype(str)
    class_labels = _ordered_class_labels(raw_labels)

    label_encoder = LabelEncoder().fit(raw_labels)
    num_classes = len(label_encoder.classes_)

    estimator = _xgboost_classifier(num_classes)
    if estimator is not None:
        model_type = "XGBoostClassifier"
        uses_label_encoder = True
        proba_class_order = [str(c) for c in label_encoder.classes_]
    else:
        estimator = _random_forest_classifier()
        model_type = "RandomForestClassifier"
        uses_label_encoder = False
        proba_class_order = None  # set from fitted classifier below

    def _encode(values: pd.Series):
        return label_encoder.transform(values) if uses_label_encoder else values

    def _decode(values) -> list[str]:
        if uses_label_encoder:
            return [str(v) for v in label_encoder.inverse_transform(values)]
        return [str(v) for v in values]

    # --- Held-out evaluation (graceful stratify fallback) ---
    can_split = len(frame) >= 8 and raw_labels.nunique() >= 2
    eval_metrics: dict = {}
    stratified = False
    evaluation_basis = "train_test_split"

    if can_split:
        x_train, x_test, y_train_raw, y_test_raw, stratified = _safe_train_test_split(
            features, raw_labels, TEST_SIZE, RANDOM_STATE
        )
        eval_pipeline = _build_pipeline(
            _xgboost_classifier(num_classes) if uses_label_encoder else _random_forest_classifier()
        )
        eval_pipeline.fit(x_train, _encode(y_train_raw))
        y_pred_raw = _decode(eval_pipeline.predict(x_test))

        try:
            proba = eval_pipeline.predict_proba(x_test)
        except Exception:  # pragma: no cover
            proba = None
        if not uses_label_encoder:
            proba_class_order = [str(c) for c in eval_pipeline.named_steps["classifier"].classes_]

        eval_metrics = _compute_metrics(
            list(y_test_raw.astype(str)), y_pred_raw, proba, proba_class_order or [], class_labels
        )
    else:
        # Too small to split: evaluate on the full data and flag it transparently.
        evaluation_basis = "full_dataset_no_split"
        full_pipeline = _build_pipeline(
            _xgboost_classifier(num_classes) if uses_label_encoder else _random_forest_classifier()
        )
        full_pipeline.fit(features, _encode(raw_labels))
        y_pred_raw = _decode(full_pipeline.predict(features))
        try:
            proba = full_pipeline.predict_proba(features)
        except Exception:  # pragma: no cover
            proba = None
        if not uses_label_encoder:
            proba_class_order = [str(c) for c in full_pipeline.named_steps["classifier"].classes_]
        eval_metrics = _compute_metrics(
            list(raw_labels.astype(str)), y_pred_raw, proba, proba_class_order or [], class_labels
        )

    # --- Final model: refit on ALL data for the persisted artifact ---
    pipeline = _build_pipeline(estimator)
    pipeline.fit(features, _encode(raw_labels))

    classes = proba_class_order if uses_label_encoder else [
        str(c) for c in pipeline.named_steps["classifier"].classes_
    ]

    bundle = {
        "pipeline": pipeline,
        "label_encoder": label_encoder if uses_label_encoder else None,
        "feature_columns": FEATURE_COLUMNS,
        "categorical_features": CATEGORICAL_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "label_column": LABEL_COLUMN,
        "classes": classes,
        "top_features": _top_feature_importances(pipeline),
        "n_samples": int(len(frame)),
        "model_type": model_type,
        "proxy_label_note": PROXY_LABEL_NOTE,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }

    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, model_path)

    metrics_artifact = {
        "model_type": model_type,
        "label_type": LABEL_TYPE,
        "n_samples": int(len(frame)),
        "n_test_samples": int(len(x_test)) if can_split else int(len(frame)),
        "test_size": TEST_SIZE,
        "random_state": RANDOM_STATE,
        "stratified": stratified,
        "evaluation_basis": evaluation_basis,
        "accuracy": eval_metrics.get("accuracy"),
        "macro_precision": eval_metrics.get("macro_precision"),
        "macro_recall": eval_metrics.get("macro_recall"),
        "macro_f1": eval_metrics.get("macro_f1"),
        "weighted_f1": eval_metrics.get("weighted_f1"),
        "roc_auc_ovr_macro": eval_metrics.get("roc_auc_ovr_macro"),
        "classification_report": eval_metrics.get("classification_report"),
        "confusion_matrix": eval_metrics.get("confusion_matrix"),
        "class_labels": eval_metrics.get("class_labels"),
        "trained_at": bundle["trained_at"],
        "evaluation_note": EVALUATION_NOTE,
    }
    if eval_metrics.get("roc_auc_note"):
        metrics_artifact["roc_auc_note"] = eval_metrics["roc_auc_note"]

    metrics_path = Path(metrics_path)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(_jsonable(metrics_artifact), handle, indent=2)

    return {
        "model_path": str(model_path),
        "metrics_path": str(metrics_path),
        "model_type": model_type,
        "n_samples": bundle["n_samples"],
        "classes": classes,
        "top_features": bundle["top_features"],
        "metrics": metrics_artifact,
    }


def main() -> None:
    result = train_and_save_model()
    metrics = result["metrics"]

    def _fmt(value) -> str:
        return "unavailable" if value is None else f"{value:.2f}"

    print("Shortage-risk model trained successfully.")
    print(f"Model: {result['model_type']}")
    print(f"Evaluation label type: {metrics['label_type']}")
    print(f"Evaluation basis: {metrics['evaluation_basis']} (stratified={metrics['stratified']})")
    print(f"Accuracy: {_fmt(metrics['accuracy'])}")
    print(f"Macro precision: {_fmt(metrics['macro_precision'])}")
    print(f"Macro recall: {_fmt(metrics['macro_recall'])}")
    print(f"Macro F1: {_fmt(metrics['macro_f1'])}")
    print(f"Weighted F1: {_fmt(metrics['weighted_f1'])}")
    print(f"ROC-AUC OVR Macro: {_fmt(metrics['roc_auc_ovr_macro'])}")
    if metrics.get("roc_auc_note"):
        print(f"  Note: {metrics['roc_auc_note']}")
    print(f"\nModel saved to:   {result['model_path']}")
    print(f"Metrics saved to: {result['metrics_path']}")
    print(f"\n{EVALUATION_NOTE}")
    print(PROXY_LABEL_NOTE)


if __name__ == "__main__":
    main()
