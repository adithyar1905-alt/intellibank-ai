from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Uuid, event
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class LedgerEntry(TimestampMixin, Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint("entry_type IN ('debit', 'credit')", name="valid_entry_type"),
        Index("ix_ledger_entries_account_created", "account_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("transactions.id", ondelete="RESTRICT"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("bank_accounts.id", ondelete="RESTRICT"), index=True
    )
    entry_type: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)

    transaction: Mapped[Transaction] = relationship(back_populates="ledger_entries")


@event.listens_for(Session, "before_flush")
def prevent_ledger_mutation(
    session: Session, flush_context: object, instances: object
) -> None:
    if any(isinstance(instance, LedgerEntry) for instance in session.deleted):
        raise ValueError("Ledger entries are immutable and cannot be deleted.")
    if any(isinstance(instance, LedgerEntry) for instance in session.dirty):
        raise ValueError("Ledger entries are immutable and cannot be updated.")