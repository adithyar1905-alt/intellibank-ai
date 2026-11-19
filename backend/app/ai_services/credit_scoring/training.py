"""Optional training pipeline for an authorized, labelled CSV dataset.

Training is intentionally separate from request-time scoring. The CSV must contain
only authorized records and a binary ``repaid`` label; no synthetic histories are
created by this component.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

FEATURE_COLUMNS = [
    "monthly_income",
    "monthly_debt",
    "requested_amount",
    "requested_term_months",
]
TARGET_COLUMN = "repaid"


def _imports() -> tuple[Any, Any, Any, Any, Any, Any]:
    try:
        import joblib
        import pandas as pd
        from sklearn.compose import ColumnTransformer
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
    except ImportError as exc:
        raise RuntimeError(
            "Training requires optional pandas, scikit-learn, and joblib dependencies."
        ) from exc
    return joblib, pd, ColumnTransformer, SimpleImputer, LogisticRegression, Pipeline


def validate_dataset(path: str | Path) -> Any:
    """Load and validate an authorized labelled CSV without inventing records."""
    _, pd, *_ = _imports()
    frame = pd.read_csv(path)
    required = set(FEATURE_COLUMNS + [TARGET_COLUMN])
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError("Dataset must contain at least one labelled row.")
    if frame[TARGET_COLUMN].isna().any() or frame[TARGET_COLUMN].nunique() != 2:
        raise ValueError("The repaid label must be complete and contain two classes.")
    if frame[FEATURE_COLUMNS].isna().any().any():
        raise ValueError("Feature values must be present; do not impute unknown histories.")
    if (frame[FEATURE_COLUMNS] < 0).any().any():
        raise ValueError("Income, debt, amount, and term must be non-negative.")
    if not set(frame[TARGET_COLUMN].unique()).issubset({0, 1, False, True}):
        raise ValueError("The repaid label must be binary (0/1).")
    return frame


def train_model(
    path: str | Path, *, model_version: str, artifact_path: str | Path | None = None
) -> dict[str, Any]:
    """Train with a held-out evaluation split and optionally persist a versioned artifact."""
    joblib, _, ColumnTransformer, SimpleImputer, LogisticRegression, Pipeline = _imports()
    from sklearn.metrics import accuracy_score, roc_auc_score
    from sklearn.model_selection import train_test_split

    frame = validate_dataset(path)
    x_train, x_test, y_train, y_test = train_test_split(
        frame[FEATURE_COLUMNS],
        frame[TARGET_COLUMN].astype(int),
        test_size=0.2,
        random_state=42,
        stratify=frame[TARGET_COLUMN],
    )
    preprocessor = ColumnTransformer(
        [("numeric", Pipeline([("imputer", SimpleImputer(strategy="median"))]), FEATURE_COLUMNS)]
    )
    model = Pipeline(
        [
            ("preprocessor", preprocessor),
            ("classifier", LogisticRegression(max_iter=1000, random_state=42)),
        ]
    )
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    probabilities = model.predict_proba(x_test)[:, 1]
    metrics = {
        "model_version": model_version,
        "rows": len(frame),
        "held_out_rows": len(x_test),
        "accuracy": float(accuracy_score(y_test, predictions)),
        "roc_auc": float(roc_auc_score(y_test, probabilities)),
    }
    if artifact_path is not None:
        joblib.dump({"model": model, "model_version": model_version}, artifact_path)
    return metrics

