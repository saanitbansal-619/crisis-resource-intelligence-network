"""
Train a baseline shortage-risk classifier and persist it.

Prefers XGBoost when available and falls back to a scikit-learn
RandomForestClassifier otherwise. Categorical features are one-hot encoded
inside a preprocessing pipeline. The model learns the transparent
simulated/proxy label, so it is a prototype forecasting aid, not a production
demand model.

Run: python -m ml_forecasting.train_model
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ml_forecasting.feature_builder import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    NUMERIC_FEATURES,
    PROXY_LABEL_NOTE,
    build_training_data,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODEL_DIR / "shortage_risk_model.joblib"


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
        random_state=42,
        eval_metric="mlogloss",
    )


def _random_forest_classifier():
    from sklearn.ensemble import RandomForestClassifier

    return RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        random_state=42,
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


def train_and_save_model(
    training_frame: pd.DataFrame | None = None,
    model_path: Path | str = MODEL_PATH,
) -> dict:
    """Train the classifier and persist a model bundle. Returns training metadata."""
    import joblib
    from sklearn.metrics import accuracy_score, classification_report
    from sklearn.model_selection import train_test_split
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

    # XGBoost needs integer targets; encode labels and remember the mapping.
    label_encoder = LabelEncoder().fit(raw_labels)
    num_classes = len(label_encoder.classes_)

    estimator = _xgboost_classifier(num_classes)
    if estimator is not None:
        model_type = "XGBClassifier"
        labels = pd.Series(label_encoder.transform(raw_labels), index=raw_labels.index)
        class_names = list(label_encoder.classes_)
        uses_label_encoder = True
    else:
        estimator = _random_forest_classifier()
        model_type = "RandomForestClassifier"
        labels = raw_labels
        class_names = None  # populated from the fitted classifier below
        uses_label_encoder = False

    pipeline = _build_pipeline(estimator)

    class_counts = raw_labels.value_counts()
    can_split = len(frame) >= 12 and class_counts.min() >= 2 and raw_labels.nunique() >= 2

    metrics: dict = {}
    report_text = ""
    if can_split:
        x_train, x_test, y_train, y_test = train_test_split(
            features, labels, test_size=0.25, random_state=42, stratify=labels
        )
        pipeline.fit(x_train, y_train)
        predictions = pipeline.predict(x_test)
        metrics["holdout_accuracy"] = round(float(accuracy_score(y_test, predictions)), 4)
        report_text = classification_report(y_test, predictions, zero_division=0)
        pipeline.fit(features, labels)  # refit on all data for the saved model
    else:
        pipeline.fit(features, labels)
        metrics["holdout_accuracy"] = None
        report_text = classification_report(
            labels, pipeline.predict(features), zero_division=0
        )

    metrics["train_accuracy"] = round(float(accuracy_score(labels, pipeline.predict(features))), 4)

    if uses_label_encoder:
        classes = class_names
    else:
        classes = [str(c) for c in pipeline.named_steps["classifier"].classes_]

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
        "metrics": metrics,
        "proxy_label_note": PROXY_LABEL_NOTE,
        "model_type": model_type,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }

    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, model_path)

    return {
        "model_path": str(model_path),
        "model_type": model_type,
        "n_samples": bundle["n_samples"],
        "classes": classes,
        "metrics": metrics,
        "top_features": bundle["top_features"],
        "classification_report": report_text,
    }


def main() -> None:
    result = train_and_save_model()
    print(f"Saved model to: {result['model_path']}")
    print(f"Model type: {result['model_type']}")
    print(f"Training samples: {result['n_samples']}")
    print(f"Classes: {result['classes']}")
    print(f"Metrics: {result['metrics']}")
    print(f"Top features: {result['top_features']}")
    print("\nClassification report:")
    print(result["classification_report"])
    print(PROXY_LABEL_NOTE)


if __name__ == "__main__":
    main()
