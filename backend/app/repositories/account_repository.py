from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.account import AccountType, BankAccount
from app.models.ledger import LedgerEntry
from app.models.transaction import Transaction


def get_account(
    session: Session, account_id: UUID, *, lock: bool = False
) -> BankAccount | None:
    statement = (
        select(BankAccount)
        .options(selectinload(BankAccount.account_type))
        .where(BankAccount.id == account_id)
    )
    if lock:
        statement = statement.with_for_update()
    return session.scalar(statement)


def get_account_types(session: Session) -> list[AccountType]:
    return list(
        session.scalars(select(AccountType).order_by(AccountType.code)).all()
    )


def search_accounts(
    session: Session,
    *,
    customer_id: UUID | None,
    query: str | None,
    status: str | None,
    account_type: str | None,
    offset: int,
    limit: int,
) -> list[BankAccount]:
    statement = (
        select(BankAccount)
        .options(selectinload(BankAccount.account_type))
        .order_by(BankAccount.created_at.desc(), BankAccount.id)
    )
    if customer_id is not None:
        statement = statement.where(BankAccount.customer_id == customer_id)
    if query:
        term = f"%{query.strip()}%"
        statement = statement.where(
            or_(BankAccount.account_number.ilike(term), BankAccount.currency.ilike(term))
        )
    if status:
        statement = statement.where(BankAccount.status == status)
    if account_type:
        statement = statement.join(AccountType).where(AccountType.code == account_type)
    return list(session.scalars(statement.offset(offset).limit(limit)).all())


def get_statement_entries(
    session: Session,
    account_id: UUID,
    *,
    start_at: datetime | None,
    end_at: datetime | None,
    offset: int,
    limit: int,
) -> list[tuple[LedgerEntry, Transaction]]:
    statement = (
        select(LedgerEntry, Transaction)
        .join(Transaction, LedgerEntry.transaction_id == Transaction.id)
        .where(LedgerEntry.account_id == account_id)
        .order_by(LedgerEntry.created_at.desc(), LedgerEntry.id)
    )
    if start_at is not None:
        statement = statement.where(LedgerEntry.created_at >= start_at)
    if end_at is not None:
        statement = statement.where(LedgerEntry.created_at < end_at)
    return list(session.execute(statement.offset(offset).limit(limit)).all())