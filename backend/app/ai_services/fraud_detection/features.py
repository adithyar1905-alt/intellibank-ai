from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.transaction import Transaction


FEATURE_COLUMNS = (
    "amount",
    "amount_to_balance_ratio",
    "transactions_last_hour",
    "transactions_last_day",
    "hour_of_day",
    "location_changed",
)


def build_transaction_features(
    session: Session,
    *,
    account_id: UUID,
    amount: Decimal,
    current_balance: Decimal,
    source_ip: str | None,
    transaction_id: UUID | None = None,
    now: datetime | None = None,
) -> dict[str, float]:
    instant = now or datetime.now(timezone.utc)
    day_ago = instant - timedelta(days=1)
    recent = session.scalars(
        select(Transaction)
        .where(
            Transaction.account_id == account_id,
            Transaction.created_at >= day_ago,
            Transaction.status != "rejected",
            *(
                (Transaction.id != transaction_id,)
                if transaction_id is not None
                else ()
            ),
        )
        .order_by(Transaction.created_at.desc())
        .limit(100)
    ).all()
    hour_ago = instant - timedelta(hours=1)
    prior_hour = 0
    for transaction in recent:
        created_at = transaction.created_at
        if created_at is None:
            continue
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if created_at >= hour_ago:
            prior_hour += 1
    prior_ips = {
        row[0]
        for row in session.execute(
            select(AuditLog.source_ip)
            .join(Transaction, AuditLog.resource_id == Transaction.id)
            .where(
                AuditLog.resource_type == "transaction",
                AuditLog.action == "transaction.create",
                Transaction.account_id == account_id,
                AuditLog.created_at >= day_ago,
                AuditLog.source_ip.is_not(None),
            )
            .limit(100)
        ).all()
    }
    return {
        "amount": float(amount),
        "amount_to_balance_ratio": float(
            amount / max(abs(current_balance), Decimal("1"))
        ),
        "transactions_last_hour": float(prior_hour + 1),
        "transactions_last_day": float(len(recent) + 1),
        "hour_of_day": float(instant.hour),
        "location_changed": float(
            bool(source_ip and prior_ips and source_ip not in prior_ips)
        ),
    }


def validate_training_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        raise ValueError("The training dataset must contain labeled transaction rows.")
    if len(rows) < 8:
        raise ValueError("At least eight labeled rows are required for held-out evaluation.")
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        unknown = set(row).difference((*FEATURE_COLUMNS, "is_fraud"))
        if unknown:
            raise ValueError(
                f"Row {index + 1} contains unsupported fields: "
                f"{', '.join(sorted(unknown))}."
            )
        if set(FEATURE_COLUMNS).difference(row) or "is_fraud" not in row:
            raise ValueError(
                f"Row {index + 1} must contain all features and the is_fraud label."
            )
        label = row["is_fraud"]
        if label not in (0, 1, False, True):
            raise ValueError(f"Row {index + 1} has an invalid is_fraud label.")
        values: dict[str, Any] = {}
        for column in FEATURE_COLUMNS:
            try:
                value = float(row[column])
            except (TypeError, ValueError):
                raise ValueError(
                    f"Row {index + 1} has a non-numeric {column} value."
                ) from None
            if not (value == value and abs(value) != float("inf")):
                raise ValueError(f"Row {index + 1} has a non-finite {column} value.")
            values[column] = value
        values["is_fraud"] = int(label)
        normalized.append(values)
    if {row["is_fraud"] for row in normalized} != {0, 1}:
        raise ValueError("Training data must include both legitimate and fraud labels.")
    return normalized
