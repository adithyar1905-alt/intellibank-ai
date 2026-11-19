from __future__ import annotations

from decimal import Decimal
from math import isfinite
from pathlib import Path
from typing import Any

from app.schemas.credit_scoring import CreditScoreResponse, FeatureExplanation

MODEL_VERSION = "indicative-v1"
LIMITATIONS = [
    "This is an indicative risk signal, not a credit decision or an approval.",
    "It uses only the applicant-declared income, debt, and requested-loan values.",
    "It does not use a credit bureau, repayment history, demographics, or inferred data.",
    "A qualified human must review the application and all applicable policy requirements.",
    "Feature explanations describe input ratios, not causal model attributions.",
]


def _band(score: int) -> str:
    if score >= 800:
        return "very_high"
    if score >= 650:
        return "high"
    if score >= 500:
        return "moderate"
    if score >= 350:
        return "low"
    return "very_low"


def _trained_probability(payload: Any, model_path: Path) -> tuple[float, str]:
    if not model_path.is_file():
        raise RuntimeError(f"Configured credit model artifact does not exist: {model_path}")
    try:
        import joblib
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "Loading a trained credit model requires pandas and joblib."
        ) from exc

    artifact = joblib.load(model_path)
    if not isinstance(artifact, dict) or "model" not in artifact:
        raise RuntimeError("Credit model artifact has an invalid format.")
    model = artifact["model"]
    if not hasattr(model, "predict_proba") or not hasattr(model, "classes_"):
        raise RuntimeError("Credit model artifact does not contain a probability model.")
    classes = list(model.classes_)
    if 1 not in classes:
        raise RuntimeError("Credit model artifact has no positive repayment class.")

    from app.ai_services.credit_scoring.training import FEATURE_COLUMNS

    features = pd.DataFrame(
        [
            {
                "monthly_income": float(payload.monthly_income),
                "monthly_debt": float(payload.monthly_debt),
                "requested_amount": float(payload.requested_amount),
                "requested_term_months": float(payload.requested_term_months),
            }
        ],
        columns=FEATURE_COLUMNS,
    )
    probabilities = model.predict_proba(features)
    probability = float(probabilities[0][classes.index(1)])
    if not isfinite(probability) or not 0 <= probability <= 1:
        raise RuntimeError("Credit model returned an invalid repayment probability.")

    version = artifact.get("model_version")
    if not isinstance(version, str) or not version.strip():
        raise RuntimeError("Credit model artifact is missing its model version.")
    return probability, version


def score_applicant(
    payload: Any, model_path: Path | None = None
) -> CreditScoreResponse:
    """Score declared affordability inputs or use a configured trained model."""
    income = Decimal(payload.monthly_income)
    debt = Decimal(payload.monthly_debt)
    amount = Decimal(payload.requested_amount)
    term = Decimal(payload.requested_term_months)
    dti = debt / income
    installment = amount / term
    affordability = (debt + installment) / income

    if model_path is None:
        # A bounded baseline is used only when no trained artifact is configured.
        score_decimal = Decimal("1000") * (
            Decimal("1") - min(affordability, Decimal("1"))
        )
        score = max(0, min(1000, int(score_decimal.quantize(Decimal("1")))))
        probability = float(Decimal(score) / Decimal("1000"))
        model_version = MODEL_VERSION
        limitations = LIMITATIONS + [
            "No trained model is configured; the score is a simple affordability heuristic."
        ]
    else:
        probability, model_version = _trained_probability(payload, model_path)
        score = int(Decimal(str(probability * 1000)).quantize(Decimal("1")))
        limitations = LIMITATIONS

    explanations = [
        FeatureExplanation(
            name="debt_to_income",
            value=dti,
            contribution=(Decimal("0.5") - dti).quantize(Decimal("0.0001")),
            explanation="Applicant-declared monthly debt divided by monthly income.",
        ),
        FeatureExplanation(
            name="requested_payment_to_income",
            value=installment / income,
            contribution=(Decimal("0.5") - installment / income).quantize(
                Decimal("0.0001")
            ),
            explanation="Requested amount divided by term, relative to monthly income.",
        ),
    ]
    return CreditScoreResponse(
        customer_id=payload.customer_id,
        score=score,
        band=_band(score),  # type: ignore[arg-type]
        probability_of_repayment=probability,
        limitations=limitations,
        explanations=explanations,
        model_version=model_version,
    )
