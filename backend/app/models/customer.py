from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'blocked')", name="valid_status"
        ),
        CheckConstraint("length(first_name) > 0", name="nonempty_first_name"),
        CheckConstraint("length(last_name) > 0", name="nonempty_last_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    customer_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    user: Mapped[User] = relationship(back_populates="customer")
    kyc_documents: Mapped[list[KYCDocument]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    accounts: Mapped[list[BankAccount]] = relationship(back_populates="customer")
    beneficiaries: Mapped[list[Beneficiary]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    loans: Mapped[list[Loan]] = relationship(back_populates="customer")
    loan_applications: Mapped[list[LoanApplication]] = relationship(
        back_populates="customer"
    )
    cards: Mapped[list[Card]] = relationship(back_populates="customer")
    fraud_alerts: Mapped[list[FraudAlert]] = relationship(back_populates="customer")
    notifications: Mapped[list[Notification]] = relationship(back_populates="customer")