from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.ai_services.fraud_detection.features import FEATURE_COLUMNS, validate_training_rows


def train_model(rows: list[dict[str, Any]], artifact_path: Path) -> dict[str, float | int]:
    """Train and evaluate a model from explicitly supplied, labeled transaction data."""
    data = validate_training_rows(rows)
    try:
        import joblib
        import numpy as np
        import pandas as pd
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as error:
        raise RuntimeError(
            "Fraud model training requires the optional pandas, numpy, scikit-learn, "
            "and joblib packages."
        ) from error

    frame = pd.DataFrame(data)
    labels = frame.pop("is_fraud")
    if labels.value_counts().min() < 2:
        raise ValueError("Each class needs at least two labeled rows for evaluation.")
    x_train, x_test, y_train, y_test = train_test_split(
        frame.loc[:, FEATURE_COLUMNS],
        labels,
        test_size=0.25,
        random_state=42,
        stratify=labels,
    )
    estimator = make_pipeline(
        StandardScaler(),
        RandomForestClassifier(
            n_estimators=200, class_weight="balanced", random_state=42
        ),
    )
    estimator.fit(x_train, y_train)
    predictions = estimator.predict(x_test)
    probabilities = estimator.predict_proba(x_test)[:, 1]
    metrics: dict[str, float | int] = {
        "sample_count": int(len(data)),
        "test_sample_count": int(len(y_test)),
        "accuracy": float(accuracy_score(y_test, predictions)),
        "precision": float(precision_score(y_test, predictions, zero_division=0)),
        "recall": float(recall_score(y_test, predictions, zero_division=0)),
        "f1": float(f1_score(y_test, predictions, zero_division=0)),
        "mean_fraud_probability": float(np.mean(probabilities)),
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": estimator, "features": list(FEATURE_COLUMNS), "metrics": metrics},
        artifact_path,
    )
    artifact_path.with_suffix(artifact_path.suffix + ".metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    return metrics
