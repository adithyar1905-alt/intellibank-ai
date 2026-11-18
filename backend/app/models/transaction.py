from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Transaction(TimestampMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency)",
            name="currency_iso_code",
        ),
        CheckConstraint(
            "transaction_type IN ('deposit', 'withdrawal', 'transfer', 'payment', "
            "'fee', 'loan_disbursement', 'loan_repayment', 'adjustment')",
            name="valid_transaction_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'completed', 'failed', 'reversed')",
            name="valid_status",
        ),
        Index("ix_transactions_account_created", "account_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("bank_accounts.id", ondelete="RESTRICT"), index=True
    )
    related_account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("bank_accounts.id", ondelete="SET NULL"), index=True
    )
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    description: Mapped[str | None] = mapped_column(String(255))

    account: Mapped[BankAccount] = relationship(
        back_populates="transactions", foreign_keys=[account_id]
    )
    related_account: Mapped[BankAccount | None] = relationship(
        back_populates="counterpart_transactions", foreign_keys=[related_account_id]
    )
    repayment: Mapped[LoanRepayment | None] = relationship(back_populates="transaction")
    fraud_alerts: Mapped[list[FraudAlert]] = relationship(back_populates="transaction")