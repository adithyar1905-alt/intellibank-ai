from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Card(TimestampMixin, Base):
    __tablename__ = "cards"
    __table_args__ = (
        CheckConstraint("length(last_four) = 4", name="last_four_digits"),
        CheckConstraint(
            "card_type IN ('debit', 'credit', 'prepaid')", name="valid_card_type"
        ),
        CheckConstraint(
            "status IN ('active', 'blocked', 'expired', 'cancelled')",
            name="valid_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("bank_accounts.id", ondelete="RESTRICT"), index=True
    )
    card_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    last_four: Mapped[str] = mapped_column(String(4), nullable=False)
    card_type: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    customer: Mapped[Customer] = relationship(back_populates="cards")
    account: Mapped[BankAccount] = relationship(back_populates="cards")