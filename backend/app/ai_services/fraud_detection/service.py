from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_services.fraud_detection.features import (
    build_transaction_features,
)
from app.config import get_settings
from app.models.account import BankAccount
from app.models.audit import AuditLog
from app.models.customer import Customer
from app.models.fraud import FraudAlert
from app.models.transaction import Transaction
from app.models.user import User


def _policy_score(features: dict[str, float], settings: Any) -> float:
    score = 0.0
    if features["amount"] >= settings.fraud_large_amount_threshold:
        score += 0.55
    if features["transactions_last_hour"] >= settings.fraud_hourly_count_threshold:
        score += 0.35
    if features["location_changed"]:
        score += 0.35
    if features["amount_to_balance_ratio"] >= 0.8:
        score += 0.2
    return min(score, 1.0)


def _model_score(features: dict[str, float], settings: Any) -> float | None:
    if settings.fraud_model_path is None:
        return None
    artifact_path = Path(settings.fraud_model_path)
    if not artifact_path.is_file():
        return None
    try:
        import joblib
        import pandas as pd
    except ImportError:
        return None
    artifact = joblib.load(artifact_path)
    estimator = artifact["model"]
    feature_names = artifact["features"]
    prediction = estimator.predict_proba(
        pd.DataFrame([{name: features[name] for name in feature_names}])
    )
    return float(prediction[0][1])


def evaluate_transaction(
    session: Session,
    transaction: Transaction,
    account: BankAccount,
    actor: User,
    source_ip: str | None,
) -> tuple[float, str, dict[str, Any]]:
    settings = get_settings()
    features = build_transaction_features(
        session,
        account_id=account.id,
        amount=transaction.amount,
        current_balance=account.current_balance,
        source_ip=source_ip,
        transaction_id=transaction.id,
    )
    rules_score = _policy_score(features, settings)
    model_score = _model_score(features, settings)
    score = max(rules_score, model_score or 0.0)
    if score >= settings.fraud_critical_threshold:
        severity = "critical"
    elif score >= settings.fraud_review_threshold:
        severity = "high"
    elif score >= settings.fraud_medium_threshold:
        severity = "medium"
    else:
        severity = "low"
    should_review = score >= settings.fraud_review_threshold
    customer = session.get(Customer, account.customer_id)
    if customer is None:
        raise RuntimeError("Account is linked to a missing customer.")
    if score >= settings.fraud_alert_threshold:
        alert = FraudAlert(
            customer_id=customer.id,
            transaction_id=transaction.id,
            score=Decimal(str(round(score, 4))),
            severity=severity,
            status="open",
            description="Transaction flagged for human fraud review."
            if should_review
            else "Transaction risk signal recorded for monitoring.",
            details={
                "features": features,
                "policy_score": rules_score,
                "model_score": model_score,
                "review_required": should_review,
                "automatic_freeze": False,
            },
        )
        session.add(alert)
        session.flush()
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="fraud.transaction_evaluated",
            resource_type="transaction",
            resource_id=transaction.id,
            source_ip=source_ip,
            details={
                "score": round(score, 4),
                "severity": severity,
                "review_required": should_review,
            },
        )
    )
    return score, severity, features


def list_alerts(session: Session, *, offset: int, limit: int) -> list[FraudAlert]:
    return list(
        session.scalars(
            select(FraudAlert)
            .order_by(FraudAlert.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )


def get_alert(session: Session, alert_id: UUID) -> FraudAlert | None:
    return session.get(FraudAlert, alert_id)


def review_alert(
    session: Session,
    alert: FraudAlert,
    actor: User,
    *,
    decision: str,
    notes: str | None,
    source_ip: str | None,
) -> FraudAlert:
    if alert.status not in {"open", "investigating"}:
        raise ValueError("Only open or investigating alerts can be reviewed.")
    transaction = (
        session.scalar(
            select(Transaction)
            .where(Transaction.id == alert.transaction_id)
            .with_for_update()
        )
        if alert.transaction_id is not None
        else None
    )
    if transaction is not None and transaction.status == "review_required":
        from app.services.transaction_service import approve_fraud_review

        approve_fraud_review(
            session,
            transaction,
            actor,
            source_ip,
            reject=decision == "reject",
        )
    alert.status = "resolved" if decision in {"approve", "reject"} else "investigating"
    alert.details = {
        **(alert.details or {}),
        "review": {
            "decision": decision,
            "reviewed_by": str(actor.id),
            "notes": notes,
        },
    }
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="fraud.alert_reviewed",
            resource_type="fraud_alert",
            resource_id=alert.id,
            source_ip=source_ip,
            details={"decision": decision, "notes": notes},
        )
    )
    session.commit()
    session.refresh(alert)
    return alert


def fraud_artifact_path() -> Path:
    settings = get_settings()
    return Path(settings.fraud_model_path or "private_models/fraud_model.joblib")


def load_training_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from app.ai_services.fraud_detection.features import validate_training_rows

    return validate_training_rows(rows)
