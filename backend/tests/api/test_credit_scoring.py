from decimal import Decimal
from uuid import uuid4

from app.ai_services.credit_scoring.engine import score_applicant
from app.schemas.credit_scoring import CreditScoreRequest


class _TrainedModel:
    classes_ = [0, 1]

    def predict_proba(self, features):
        assert list(features.columns) == [
            "monthly_income",
            "monthly_debt",
            "requested_amount",
            "requested_term_months",
        ]
        return [[0.2, 0.8]]


def test_score_uses_only_declared_affordability_inputs() -> None:
    payload = CreditScoreRequest(
        customer_id=uuid4(),
        monthly_income=Decimal("10000"),
        monthly_debt=Decimal("1000"),
        requested_amount=Decimal("12000"),
        requested_term_months=12,
    )
    result = score_applicant(payload)
    assert 0 <= result.score <= 1000
    assert result.indicative_only is True
    assert result.human_review_required is True
    assert any("not a credit decision" in item for item in result.limitations)
    assert {item.name for item in result.explanations} == {
        "debt_to_income",
        "requested_payment_to_income",
    }


def test_score_uses_configured_trained_model(tmp_path, monkeypatch) -> None:
    import joblib

    model_path = tmp_path / "credit-model.joblib"
    model_path.touch()
    monkeypatch.setattr(
        joblib,
        "load",
        lambda path: {"model": _TrainedModel(), "model_version": "test-v2"},
    )
    payload = CreditScoreRequest(
        customer_id=uuid4(),
        monthly_income=Decimal("10000"),
        monthly_debt=Decimal("1000"),
        requested_amount=Decimal("12000"),
        requested_term_months=12,
    )

    result = score_applicant(payload, model_path=model_path)

    assert result.score == 800
    assert result.probability_of_repayment == 0.8
    assert result.model_version == "test-v2"
    assert result.human_review_required is True
    assert not any("No trained model is configured" in item for item in result.limitations)


def test_missing_configured_model_does_not_fall_back_to_baseline(tmp_path) -> None:
    payload = CreditScoreRequest(
        customer_id=uuid4(),
        monthly_income=Decimal("10000"),
        monthly_debt=Decimal("1000"),
        requested_amount=Decimal("12000"),
        requested_term_months=12,
    )

    try:
        score_applicant(payload, model_path=tmp_path / "missing.joblib")
    except RuntimeError as error:
        assert "does not exist" in str(error)
    else:
        raise AssertionError("a configured missing model must not silently use the baseline")


def test_invalid_applicant_values_are_rejected() -> None:
    try:
        CreditScoreRequest(
            customer_id=uuid4(),
            monthly_income=0,
            monthly_debt=1,
            requested_amount=1,
            requested_term_months=12,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("zero income must be rejected")
