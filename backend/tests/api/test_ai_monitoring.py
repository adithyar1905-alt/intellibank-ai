from __future__ import annotations

from collections.abc import Generator
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.aml import AMLCase
from app.models.fraud import FraudAlert
from tests.api.test_financial_modules import banking_api


@pytest.fixture(autouse=True)
def monitoring_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> Generator[None, None, None]:
    monkeypatch.setenv("FRAUD_LARGE_AMOUNT_THRESHOLD", "10000")
    monkeypatch.setenv("FRAUD_HOURLY_COUNT_THRESHOLD", "8")
    monkeypatch.setenv("FRAUD_ALERT_THRESHOLD", "0.35")
    monkeypatch.setenv("FRAUD_MEDIUM_THRESHOLD", "0.35")
    monkeypatch.setenv("FRAUD_REVIEW_THRESHOLD", "0.7")
    monkeypatch.setenv("FRAUD_CRITICAL_THRESHOLD", "0.9")
    monkeypatch.setenv(
        "FRAUD_MODEL_PATH", str(tmp_path / "untrained-fraud-model.joblib")
    )
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _create_active_account(client, customer_id) -> str:
    opened = client.post(
        "/api/v1/accounts",
        json={
            "customer_id": str(customer_id),
            "account_type": "savings",
            "currency": "USD",
        },
    )
    assert opened.status_code == 201, opened.text
    account_id = opened.json()["id"]
    approved = client.post(f"/api/v1/accounts/{account_id}/approve")
    assert approved.status_code == 200, approved.text
    active = client.post(f"/api/v1/accounts/{account_id}/activate")
    assert active.status_code == 200, active.text
    return account_id


@pytest.fixture
def monitoring_api(banking_api: dict[str, Any]) -> dict[str, Any]:
    return banking_api


def test_fraud_hold_requires_human_review_and_aml_case_can_be_closed(
    monitoring_api: dict[str, Any],
) -> None:
    api = monitoring_api
    client = api["client"]
    account_id = _create_active_account(client, api["customer_id"])

    created = client.post(
        "/api/v1/transactions",
        headers={"Idempotency-Key": "fraud-review-key-0001"},
        json={
            "account_id": account_id,
            "transaction_type": "deposit",
            "amount": "20000.00",
            "description": "Large deposit for review",
        },
    )
    assert created.status_code == 201, created.text
    transaction = created.json()
    assert transaction["status"] == "review_required"

    balance = client.get(f"/api/v1/accounts/{account_id}/balance")
    assert balance.status_code == 200
    assert balance.json()["current_balance"] == "0.0000"
    assert balance.json()["status"] == "active"

    with Session(api["engine"]) as session:
        alert = session.scalar(
            select(FraudAlert).where(
                FraudAlert.transaction_id == UUID(transaction["id"])
            )
        )
        aml_case = session.scalar(
            select(AMLCase).where(
                AMLCase.transaction_id == UUID(transaction["id"])
            )
        )
        assert alert is not None
        assert alert.severity in {"high", "critical"}
        assert alert.details["automatic_freeze"] is False
        assert aml_case is not None
        assert aml_case.rule_code == "large_transaction"
        assert aml_case.status == "open"
        alert_id = str(alert.id)
        case_id = str(aml_case.id)

    reviewed = client.post(
        f"/api/v1/fraud/alerts/{alert_id}/review",
        json={"decision": "approve", "notes": "Reviewed by risk analyst."},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "resolved"

    after_review = client.get(f"/api/v1/accounts/{account_id}/balance")
    assert after_review.status_code == 200
    assert after_review.json()["current_balance"] == "20000.0000"

    investigating = client.patch(
        f"/api/v1/aml/cases/{case_id}",
        json={
            "status": "investigating",
            "assigned_to": str(api["staff_user_id"]),
        },
    )
    assert investigating.status_code == 200, investigating.text
    assert investigating.json()["status"] == "investigating"

    closed = client.patch(
        f"/api/v1/aml/cases/{case_id}",
        json={"status": "closed", "resolution": "Source of funds verified."},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"
    summary = client.get("/api/v1/aml/reports/summary")
    assert summary.status_code == 200
    assert summary.json()["total_cases"] == 1
    assert summary.json()["by_status"]["closed"] == 1


def test_aml_rules_are_configurable_and_validated(
    monitoring_api: dict[str, Any],
) -> None:
    client = monitoring_api["client"]
    changed = client.put(
        "/api/v1/aml/rules/large_transaction",
        json={
            "description": "Updated threshold for the compliance test.",
            "enabled": False,
            "parameters": {"amount_threshold": 15000},
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["enabled"] is False

    invalid = client.put(
        "/api/v1/aml/rules/large_transaction",
        json={
            "description": "Invalid threshold",
            "enabled": True,
            "parameters": {"amount_threshold": -1},
        },
    )
    assert invalid.status_code == 422


def test_customer_cannot_read_investigator_queues(
    monitoring_api: dict[str, Any],
) -> None:
    api = monitoring_api
    api["current_actor"]["id"] = api["customer_user_id"]
    client = api["client"]
    assert client.get("/api/v1/fraud/alerts").status_code == 403
    assert client.get("/api/v1/aml/cases").status_code == 403


def test_fraud_training_rows_require_real_labeled_feature_shape() -> None:
    from app.ai_services.fraud_detection.features import (
        FEATURE_COLUMNS,
        validate_training_rows,
    )

    rows = [
        {**{column: float(index) for column in FEATURE_COLUMNS}, "is_fraud": label}
        for label in (0, 0, 0, 0, 1, 1, 1, 1)
        for index in (label,)
    ]
    assert len(validate_training_rows(rows)) == 8
    with pytest.raises(ValueError, match="both legitimate and fraud labels"):
        validate_training_rows([rows[0] for _ in range(8)])


def test_fraud_model_training_returns_evaluation_metrics_and_saves_artifact(
    tmp_path,
) -> None:
    from app.ai_services.fraud_detection.features import FEATURE_COLUMNS
    from app.ai_services.fraud_detection.model import train_model

    rows = []
    for index in range(40):
        label = index % 2
        rows.append(
            {
                **{
                    column: float(index + label * 2)
                    for column in FEATURE_COLUMNS
                },
                "is_fraud": label,
            }
        )
    artifact = tmp_path / "fraud-model.joblib"
    metrics = train_model(rows, artifact)

    assert artifact.is_file()
    assert (tmp_path / "fraud-model.joblib.metrics.json").is_file()
    assert metrics["sample_count"] == 40
    assert metrics["test_sample_count"] == 10
    assert 0 <= metrics["precision"] <= 1
