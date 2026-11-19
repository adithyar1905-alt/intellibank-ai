from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import secrets
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import BankAccount
from app.models.aml import AMLCase, AMLRule
from app.models.audit import AuditLog
from app.models.fraud import FraudAlert
from app.models.transaction import Transaction
from app.models.user import User


DEFAULT_RULES: dict[str, tuple[str, dict[str, Any]]] = {
    "large_transaction": (
        "Single transaction exceeds the configured review threshold.",
        {"amount_threshold": 10000.0},
    ),
    "rapid_transactions": (
        "Multiple transactions in a short interval exceed configured thresholds.",
        {"count_threshold": 5, "window_minutes": 10, "total_threshold": 5000.0},
    ),
    "high_risk_customer": (
        "Customer has repeated unresolved high-risk fraud alerts.",
        {"alert_count_threshold": 3, "minimum_score": 0.8},
    ),
    "external_transfer": (
        "External payment rail transaction requires compliance screening.",
        {"transaction_types": ["neft", "rtgs", "imps", "upi"], "minimum_amount": 5000.0},
    ),
}


def _enabled_rules(session: Session) -> dict[str, dict[str, Any]]:
    configured = {
        rule.code: rule
        for rule in session.scalars(select(AMLRule)).all()
    }
    return {
        code: {
            "enabled": configured[code].enabled if code in configured else True,
            "parameters": configured[code].parameters
            if code in configured
            else parameters,
        }
        for code, (description, parameters) in DEFAULT_RULES.items()
    }


def evaluate_transaction(
    session: Session,
    transaction: Transaction,
    source_ip: str | None = None,
) -> list[AMLCase]:
    account = session.get(BankAccount, transaction.account_id)
    if account is None:
        raise RuntimeError("Transaction is linked to a missing account.")
    rules = _enabled_rules(session)
    matched: list[tuple[str, str, dict[str, Any]]] = []

    large = rules["large_transaction"]["parameters"]
    if rules["large_transaction"]["enabled"] and float(transaction.amount) >= float(
        large["amount_threshold"]
    ):
        matched.append(
            (
                "large_transaction",
                "high",
                {"amount": str(transaction.amount), "threshold": large["amount_threshold"]},
            )
        )

    rapid = rules["rapid_transactions"]["parameters"]
    window_minutes = int(rapid["window_minutes"])
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    recent = session.scalars(
        select(Transaction).where(
            Transaction.account_id == transaction.account_id,
            Transaction.created_at >= cutoff,
            Transaction.status != "rejected",
        )
    ).all()
    recent_total = sum((item.amount for item in recent), start=0)
    if (
        rules["rapid_transactions"]["enabled"]
        and len(recent) >= int(rapid["count_threshold"])
        and float(recent_total) >= float(rapid["total_threshold"])
    ):
        matched.append(
            (
                "rapid_transactions",
                "high",
                {
                    "count": len(recent),
                    "window_minutes": window_minutes,
                    "total_amount": str(recent_total),
                },
            )
        )

    customer_alerts = session.scalars(
        select(FraudAlert).where(
            FraudAlert.customer_id == account.customer_id,
            FraudAlert.status.in_(("open", "investigating", "confirmed")),
            FraudAlert.score >= float(
                rules["high_risk_customer"]["parameters"]["minimum_score"]
            ),
        )
    ).all()
    risk_parameters = rules["high_risk_customer"]["parameters"]
    if (
        rules["high_risk_customer"]["enabled"]
        and len(customer_alerts) >= int(risk_parameters["alert_count_threshold"])
    ):
        matched.append(
            (
                "high_risk_customer",
                "critical",
                {
                    "unresolved_high_risk_alerts": len(customer_alerts),
                    "minimum_score": risk_parameters["minimum_score"],
                },
            )
        )

    external = rules["external_transfer"]["parameters"]
    if (
        rules["external_transfer"]["enabled"]
        and transaction.transaction_type in external["transaction_types"]
        and float(transaction.amount) >= float(external["minimum_amount"])
    ):
        matched.append(
            (
                "external_transfer",
                "medium",
                {
                    "transaction_type": transaction.transaction_type,
                    "amount": str(transaction.amount),
                    "minimum_amount": external["minimum_amount"],
                },
            )
        )

    cases: list[AMLCase] = []
    for rule_code, severity, finding in matched:
        existing = session.scalar(
            select(AMLCase).where(
                AMLCase.transaction_id == transaction.id,
                AMLCase.rule_code == rule_code,
            )
        )
        if existing is not None:
            cases.append(existing)
            continue
        case = AMLCase(
            case_number=f"AML-{secrets.token_hex(8).upper()}",
            customer_id=account.customer_id,
            transaction_id=transaction.id,
            rule_code=rule_code,
            severity=severity,
            status="open",
            findings={
                **finding,
                "transaction_reference": transaction.reference,
                "source_ip": source_ip,
                "human_review_required": True,
            },
        )
        session.add(case)
        session.flush()
        cases.append(case)
        session.add(
            AuditLog(
                actor_id=transaction.initiated_by,
                action="aml.case_created",
                resource_type="aml_case",
                resource_id=case.id,
                source_ip=source_ip,
                details={"rule_code": rule_code, "severity": severity},
            )
        )
    session.flush()
    return cases


def list_cases(
    session: Session, *, offset: int, limit: int, status_filter: str | None = None
) -> list[AMLCase]:
    statement = select(AMLCase).order_by(AMLCase.created_at.desc())
    if status_filter is not None:
        statement = statement.where(AMLCase.status == status_filter)
    return list(session.scalars(statement.offset(offset).limit(limit)).all())


def get_case(session: Session, case_id: UUID) -> AMLCase | None:
    return session.get(AMLCase, case_id)


def update_case(
    session: Session,
    case: AMLCase,
    actor: User,
    *,
    status: str,
    assigned_to: UUID | None,
    resolution: str | None,
    source_ip: str | None,
) -> AMLCase:
    valid_transitions = {
        "open": {"investigating"},
        "investigating": {"escalated", "closed"},
        "escalated": {"investigating", "closed"},
        "closed": set(),
    }
    if status not in valid_transitions[case.status]:
        raise ValueError(
            f"AML case cannot transition from {case.status} to {status}."
        )
    if status == "closed" and not resolution:
        raise ValueError("A resolution is required to close an AML case.")
    if assigned_to is not None and session.get(User, assigned_to) is None:
        raise ValueError("Assigned investigator was not found.")
    case.status = status
    case.assigned_to = assigned_to
    case.resolution = resolution
    case.closed_at = datetime.now(timezone.utc) if status == "closed" else None
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="aml.case_updated",
            resource_type="aml_case",
            resource_id=case.id,
            source_ip=source_ip,
            details={
                "status": status,
                "assigned_to": str(assigned_to) if assigned_to else None,
                "resolution": resolution,
            },
        )
    )
    session.commit()
    session.refresh(case)
    return case


def upsert_rule(
    session: Session, code: str, values: dict[str, Any], actor: User, source_ip: str | None
) -> AMLRule:
    if code not in DEFAULT_RULES:
        raise ValueError("Unknown AML rule.")
    parameters = values["parameters"]
    expected_parameters = set(DEFAULT_RULES[code][1])
    if set(parameters) != expected_parameters:
        raise ValueError(
            f"Rule parameters must contain exactly: {', '.join(sorted(expected_parameters))}."
        )
    for key, value in parameters.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            if not (
                code == "external_transfer"
                and key == "transaction_types"
                and isinstance(value, list)
                and value
                and all(item in {"neft", "rtgs", "imps", "upi"} for item in value)
            ):
                raise ValueError(f"Rule parameter {key} must be a positive number.")
    current = session.get(AMLRule, code)
    rule = current or AMLRule(code=code, **values)
    if current is not None:
        for key, value in values.items():
            setattr(rule, key, value)
    session.add(rule)
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="aml.rule_updated",
            resource_type="aml_rule",
            resource_id=None,
            source_ip=source_ip,
            details={"rule_code": code, "enabled": values["enabled"]},
        )
    )
    session.commit()
    session.refresh(rule)
    return rule


def list_rules(session: Session) -> list[AMLRule]:
    configured = {rule.code: rule for rule in session.scalars(select(AMLRule)).all()}
    return [
        configured[code]
        if code in configured
        else AMLRule(
            code=code,
            description=description,
            enabled=True,
            parameters=parameters,
        )
        for code, (description, parameters) in DEFAULT_RULES.items()
    ]


def report_summary(session: Session) -> dict[str, Any]:
    total = session.scalar(select(func.count()).select_from(AMLCase)) or 0
    statuses = session.execute(
        select(AMLCase.status, func.count()).group_by(AMLCase.status)
    ).all()
    severities = session.execute(
        select(AMLCase.severity, func.count()).group_by(AMLCase.severity)
    ).all()
    return {
        "total_cases": total,
        "by_status": {status: count for status, count in statuses},
        "by_severity": {severity: count for severity, count in severities},
    }
