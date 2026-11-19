from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AccountType(TimestampMixin, Base):
    __tablename__ = "account_types"
    __table_args__ = (
        CheckConstraint("minimum_balance >= 0", name="nonnegative_minimum_balance"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    minimum_balance: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0")
    )
    allows_overdraft: Mapped[bool] = mapped_column(nullable=False, default=False)

    accounts: Mapped[list[BankAccount]] = relationship(back_populates="account_type")


class BankAccount(TimestampMixin, Base):
    __tablename__ = "bank_accounts"
    __table_args__ = (
        CheckConstraint("overdraft_limit >= 0", name="nonnegative_overdraft_limit"),
        CheckConstraint("daily_limit > 0", name="positive_daily_limit"),
        CheckConstraint("monthly_limit > 0", name="positive_monthly_limit"),
        CheckConstraint(
            "current_balance >= -overdraft_limit", name="balance_within_overdraft"
        ),
        CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency)",
            name="currency_iso_code",
        ),
        CheckConstraint(
            "status IN ('pending_approval', 'pending_activation', 'active', "
            "'frozen', 'closed')",
            name="valid_status",
        ),
        Index("ix_bank_accounts_customer_status", "customer_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    account_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("account_types.id", ondelete="RESTRICT"), index=True
    )
    account_number: Mapped[str] = mapped_column(String(34), unique=True, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    current_balance: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0")
    )
    overdraft_limit: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0")
    )
    daily_limit: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("10000")
    )
    monthly_limit: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("100000")
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    customer: Mapped[Customer] = relationship(back_populates="accounts")
    account_type: Mapped[AccountType] = relationship(back_populates="accounts")
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="account", foreign_keys="Transaction.account_id"
    )
    counterpart_transactions: Mapped[list[Transaction]] = relationship(
        back_populates="related_account", foreign_keys="Transaction.related_account_id"
    )
    beneficiaries: Mapped[list[Beneficiary]] = relationship(
        back_populates="linked_account", foreign_keys="Beneficiary.linked_account_id"
    )
    loans: Mapped[list[Loan]] = relationship(back_populates="account")
    cards: Mapped[list[Card]] = relationship(back_populates="account")