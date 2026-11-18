from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class FraudAlert(TimestampMixin, Base):
    __tablename__ = "fraud_alerts"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 1", name="score_between_zero_and_one"),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="valid_severity",
        ),
        CheckConstraint(
            "status IN ('open', 'investigating', 'confirmed', 'dismissed', 'resolved')",
            name="valid_status",
        ),
        Index("ix_fraud_alerts_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("transactions.id", ondelete="SET NULL"), index=True
    )
    score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    customer: Mapped[Customer] = relationship(back_populates="fraud_alerts")
    transaction: Mapped[Transaction | None] = relationship(back_populates="fraud_alerts")