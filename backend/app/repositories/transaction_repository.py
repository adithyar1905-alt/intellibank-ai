from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.models.ledger import LedgerEntry
from app.models.transaction import Transaction


def get_transaction(
    session: Session, transaction_id: UUID, *, lock: bool = False
) -> Transaction | None:
    statement = select(Transaction).where(Transaction.id == transaction_id)
    if lock:
        statement = statement.with_for_update()
    return session.scalar(statement)


def get_transaction_for_idempotency(
    session: Session, key: str
) -> Transaction | None:
    return session.scalar(
        select(Transaction).where(Transaction.idempotency_key == key)
    )


def list_account_transactions(
    session: Session, account_id: UUID, *, offset: int, limit: int
) -> list[Transaction]:
    statement = (
        select(Transaction)
        .join(LedgerEntry, LedgerEntry.transaction_id == Transaction.id)
        .where(LedgerEntry.account_id == account_id)
        .order_by(Transaction.created_at.desc(), Transaction.id)
        .offset(offset)
        .limit(limit)
    )
    return list(session.scalars(statement).unique().all())


def daily_outbound_total(session: Session, account_id: UUID, day: date) -> Decimal:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = datetime.combine(day, time.max, tzinfo=timezone.utc)
    amount = session.scalar(
        select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
            LedgerEntry.account_id == account_id,
            LedgerEntry.entry_type == "debit",
            LedgerEntry.created_at >= start,
            LedgerEntry.created_at <= end,
        )
    )
    return Decimal(amount)


def monthly_outbound_total(session: Session, account_id: UUID, day: date) -> Decimal:
    start = datetime(day.year, day.month, 1, tzinfo=timezone.utc)
    amount = session.scalar(
        select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
            LedgerEntry.account_id == account_id,
            LedgerEntry.entry_type == "debit",
            LedgerEntry.created_at >= start,
        )
    )
    return Decimal(amount)


def daily_summary(
    session: Session, account_id: UUID, day: date
) -> tuple[int, Decimal, int, Decimal]:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = datetime.combine(day, time.max, tzinfo=timezone.utc)
    row = session.execute(
        select(
            func.count(case((LedgerEntry.entry_type == "debit", 1))),
            func.coalesce(
                func.sum(case((LedgerEntry.entry_type == "debit", LedgerEntry.amount), else_=0)),
                0,
            ),
            func.count(case((LedgerEntry.entry_type == "credit", 1))),
            func.coalesce(
                func.sum(case((LedgerEntry.entry_type == "credit", LedgerEntry.amount), else_=0)),
                0,
            ),
        ).where(
            LedgerEntry.account_id == account_id,
            LedgerEntry.created_at >= start,
            LedgerEntry.created_at <= end,
        )
    ).one()
    return int(row[0]), Decimal(row[1]), int(row[2]), Decimal(row[3])