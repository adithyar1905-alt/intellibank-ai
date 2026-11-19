from uuid import UUID

from sqlalchemy import case, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.account import BankAccount
from app.models.customer import Customer
from app.models.fraud import FraudAlert
from app.models.transaction import Transaction
from app.models.user import User


def get_customer(session: Session, customer_id: UUID) -> Customer | None:
    return session.scalar(
        select(Customer)
        .options(
            selectinload(Customer.user),
            selectinload(Customer.kyc_documents),
        )
        .where(Customer.id == customer_id)
    )


def search_customers(
    session: Session,
    *,
    query: str | None,
    status: str | None,
    offset: int,
    limit: int,
) -> list[Customer]:
    statement = (
        select(Customer)
        .join(User, Customer.user_id == User.id)
        .options(
            selectinload(Customer.user),
            selectinload(Customer.kyc_documents),
        )
        .order_by(Customer.created_at.desc(), Customer.id)
    )
    if query:
        term = f"%{query.strip()}%"
        statement = statement.where(
            or_(
                Customer.first_name.ilike(term),
                Customer.last_name.ilike(term),
                Customer.customer_number.ilike(term),
                User.email.ilike(term),
                User.phone_number.ilike(term),
            )
        )
    if status:
        statement = statement.where(Customer.status == status)
    return list(session.scalars(statement.offset(offset).limit(limit)).all())


def get_account_history(
    session: Session, customer_id: UUID, *, offset: int, limit: int
) -> list[tuple[Transaction, BankAccount]]:
    customer_account_ids = select(BankAccount.id).where(
        BankAccount.customer_id == customer_id
    )
    account_id = case(
        (
            Transaction.account_id.in_(customer_account_ids),
            Transaction.account_id,
        ),
        else_=Transaction.related_account_id,
    )
    statement = (
        select(Transaction, BankAccount)
        .join(BankAccount, account_id == BankAccount.id)
        .order_by(Transaction.created_at.desc(), Transaction.id)
        .offset(offset)
        .limit(limit)
    )
    return list(session.execute(statement).all())


def get_customer_alerts(
    session: Session, customer_id: UUID
) -> list[FraudAlert]:
    statement = (
        select(FraudAlert)
        .where(FraudAlert.customer_id == customer_id)
        .order_by(FraudAlert.created_at.desc(), FraudAlert.id)
    )
    return list(session.scalars(statement).all())