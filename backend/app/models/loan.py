from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    func,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Loan(TimestampMixin, Base):
    __tablename__ = "loans"
    __table_args__ = (
        CheckConstraint("principal > 0", name="positive_principal"),
        CheckConstraint("interest_rate >= 0", name="nonnegative_interest_rate"),
        CheckConstraint("term_months > 0", name="positive_term"),
        CheckConstraint(
            "status IN ('active', 'paid_off', 'defaulted', 'closed', 'pending_disbursement')",
            name="valid_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("bank_accounts.id", ondelete="SET NULL"), index=True
    )
    principal: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    term_months: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    loan_type: Mapped[str] = mapped_column(String(30), nullable=False, default="personal")
    outstanding_balance: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0")
    )

    customer: Mapped[Customer] = relationship(back_populates="loans")
    account: Mapped[BankAccount | None] = relationship(back_populates="loans")
    application: Mapped[LoanApplication | None] = relationship(
        back_populates="loan", uselist=False
    )
    repayments: Mapped[list[LoanRepayment]] = relationship(
        back_populates="loan", cascade="all, delete-orphan"
    )


class LoanApplication(TimestampMixin, Base):
    __tablename__ = "loan_applications"
    __table_args__ = (
        CheckConstraint("requested_amount > 0", name="positive_requested_amount"),
        CheckConstraint(
            "requested_term_months > 0", name="positive_requested_term"
        ),
        CheckConstraint(
            "status IN ('submitted', 'under_review', 'approved', 'rejected', "
            "'withdrawn', 'disbursed')",
            name="valid_status",
        ),
        UniqueConstraint("loan_id", name="uq_loan_applications_loan_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    loan_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("loans.id", ondelete="SET NULL")
    )
    disbursement_account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("bank_accounts.id", ondelete="RESTRICT")
    )
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    declared_monthly_income: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0")
    )
    requested_term_months: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="submitted")
    loan_type: Mapped[str] = mapped_column(String(30), nullable=False, default="personal")
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    customer: Mapped[Customer] = relationship(back_populates="loan_applications")
    loan: Mapped[Loan | None] = relationship(back_populates="application")
    documents: Mapped[list[LoanDocument]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class LoanRepayment(TimestampMixin, Base):
    __tablename__ = "loan_repayments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint("principal_amount >= 0", name="nonnegative_principal_amount"),
        CheckConstraint("interest_amount >= 0", name="nonnegative_interest_amount"),
        CheckConstraint(
            "status IN ('scheduled', 'paid', 'late', 'missed')", name="valid_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    loan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("loans.id", ondelete="CASCADE"), index=True
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("transactions.id", ondelete="SET NULL"),
        unique=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    principal_amount: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0")
    )
    interest_amount: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0")
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")

    loan: Mapped[Loan] = relationship(back_populates="repayments")
    transaction: Mapped[Transaction | None] = relationship(back_populates="repayment")


class LoanDocument(TimestampMixin, Base):
    __tablename__ = "loan_documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("loan_applications.id", ondelete="CASCADE"), index=True
    )
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    document_reference: Mapped[str] = mapped_column(String(512), nullable=False)

    application: Mapped[LoanApplication] = relationship(back_populates="documents")