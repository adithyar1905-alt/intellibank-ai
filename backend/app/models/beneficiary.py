from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Beneficiary(TimestampMixin, Base):
    __tablename__ = "beneficiaries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'disabled')", name="valid_status"
        ),
        CheckConstraint(
            "ifsc_code IS NULL OR length(ifsc_code) = 11", name="valid_ifsc_length"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    linked_account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("bank_accounts.id", ondelete="SET NULL"), index=True
    )
    beneficiary_name: Mapped[str] = mapped_column(String(160), nullable=False)
    account_number: Mapped[str] = mapped_column(String(34), nullable=False, index=True)
    bank_name: Mapped[str | None] = mapped_column(String(120))
    ifsc_code: Mapped[str | None] = mapped_column(String(11))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    customer: Mapped[Customer] = relationship(back_populates="beneficiaries")
    linked_account: Mapped[BankAccount | None] = relationship(
        back_populates="beneficiaries", foreign_keys=[linked_account_id]
    )