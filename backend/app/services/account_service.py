from __future__ import annotations

from datetime import datetime, timezone
import secrets
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.account import AccountType, BankAccount
from app.models.audit import AuditLog
from app.models.customer import Customer
from app.models.user import User
from app.repositories.account_repository import (
    get_account,
    get_account_types,
    get_statement_entries,
    search_accounts,
)
from app.schemas.account import (
    AccountBalanceResponse,
    AccountLimitsUpdate,
    AccountOpenRequest,
    AccountStatementItem,
    AccountStatementResponse,
    AccountTypeResponse,
)


STAFF_ROLES = ("Super Admin", "Bank Admin", "Branch Manager", "Bank Employee")
ACCOUNT_APPROVER_ROLES = ("Super Admin", "Bank Admin", "Branch Manager")


def has_role(user: User, roles: tuple[str, ...]) -> bool:
    assigned = {role.name for role in user.roles}
    return "Super Admin" in assigned or bool(assigned.intersection(roles))


def require_account(
    session: Session, account_id: UUID, *, lock: bool = False
) -> BankAccount:
    account = get_account(session, account_id, lock=lock)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found."
        )
    return account


def require_account_access(account: BankAccount, actor: User) -> None:
    if has_role(actor, STAFF_ROLES):
        return
    if actor.customer is not None and actor.customer.id == account.customer_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You are not allowed to access this account.",
    )


def write_account_audit(
    session: Session,
    actor: User,
    action: str,
    account: BankAccount,
    source_ip: str | None,
    details: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_id=actor.id,
            action=action,
            resource_type="bank_account",
            resource_id=account.id,
            source_ip=source_ip,
            details=details or {},
        )
    )


def account_response(account: BankAccount) -> dict[str, object]:
    return {
        "id": account.id,
        "customer_id": account.customer_id,
        "account_type": account.account_type.code,
        "account_number_last4": account.account_number[-4:],
        "currency": account.currency,
        "current_balance": account.current_balance,
        "overdraft_limit": account.overdraft_limit,
        "daily_limit": account.daily_limit,
        "monthly_limit": account.monthly_limit,
        "status": account.status,
        "approved_at": account.approved_at,
        "closed_at": account.closed_at,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }


def list_account_types(session: Session) -> list[AccountTypeResponse]:
    return [
        AccountTypeResponse.model_validate(
            {
                "code": item.code,
                "name": item.name,
                "minimum_balance": item.minimum_balance,
                "allows_overdraft": item.allows_overdraft,
            }
        )
        for item in get_account_types(session)
    ]


def open_account(
    session: Session,
    payload: AccountOpenRequest,
    actor: User,
    source_ip: str | None,
) -> BankAccount:
    customer = session.scalar(
        select(Customer).where(Customer.id == payload.customer_id)
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    if customer.status != "active" or not customer.user.is_active:
        raise HTTPException(
            status_code=409, detail="An active customer is required to open an account."
        )
    if not has_role(actor, STAFF_ROLES) and (
        actor.customer is None or actor.customer.id != customer.id
    ):
        raise HTTPException(
            status_code=403, detail="You are not allowed to open an account for this customer."
        )
    account_type = session.scalar(
        select(AccountType).where(AccountType.code == payload.account_type)
    )
    if account_type is None:
        raise HTTPException(
            status_code=503,
            detail="Account types are not provisioned. Apply database migrations.",
        )
    if payload.currency != "USD":
        raise HTTPException(
            status_code=422,
            detail="Only USD accounts are currently supported.",
        )
    for _ in range(5):
        account_number = f"{secrets.randbelow(10**15):015d}"
        if session.scalar(
            select(BankAccount.id).where(BankAccount.account_number == account_number)
        ) is None:
            break
    else:
        raise HTTPException(
            status_code=503, detail="Unable to generate a unique account number."
        )
    account = BankAccount(
        customer_id=customer.id,
        account_type=account_type,
        account_number=account_number,
        currency=payload.currency,
        current_balance=0,
        overdraft_limit=0,
        status="pending_approval",
    )
    session.add(account)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=503, detail="Unable to generate a unique account number."
        ) from None
    write_account_audit(
        session,
        actor,
        "account.open",
        account,
        source_ip,
        {"customer_id": str(customer.id), "account_type": account_type.code},
    )
    session.commit()
    return require_account(session, account.id)


def transition_account(
    session: Session,
    account_id: UUID,
    transition: str,
    actor: User,
    source_ip: str | None,
) -> BankAccount:
    account = require_account(session, account_id, lock=True)
    old_status = account.status
    now = datetime.now(timezone.utc)
    if transition == "approve":
        if not has_role(actor, ACCOUNT_APPROVER_ROLES):
            raise HTTPException(status_code=403, detail="Account approval role required.")
        if account.status != "pending_approval":
            raise HTTPException(status_code=409, detail="Account is not awaiting approval.")
        account.status = "pending_activation"
        account.approved_by = actor.id
        account.approved_at = now
    elif transition == "activate":
        if not has_role(actor, STAFF_ROLES):
            raise HTTPException(status_code=403, detail="Bank staff role required.")
        if account.status != "pending_activation":
            raise HTTPException(status_code=409, detail="Account is not awaiting activation.")
        account.status = "active"
    elif transition == "freeze":
        if not has_role(actor, ACCOUNT_APPROVER_ROLES):
            raise HTTPException(status_code=403, detail="Account manager role required.")
        if account.status != "active":
            raise HTTPException(status_code=409, detail="Only active accounts can be frozen.")
        account.status = "frozen"
    elif transition == "unfreeze":
        if not has_role(actor, ACCOUNT_APPROVER_ROLES):
            raise HTTPException(status_code=403, detail="Account manager role required.")
        if account.status != "frozen":
            raise HTTPException(status_code=409, detail="Only frozen accounts can be unfrozen.")
        account.status = "active"
    elif transition == "close":
        if not has_role(actor, STAFF_ROLES):
            require_account_access(account, actor)
        if account.status not in {"active", "frozen", "pending_approval", "pending_activation"}:
            raise HTTPException(status_code=409, detail="Account is already closed.")
        if account.current_balance != 0:
            raise HTTPException(
                status_code=409,
                detail="Account balance must be zero before closure.",
            )
        account.status = "closed"
        account.closed_at = now
    else:
        raise ValueError(f"Unknown account transition: {transition}")
    write_account_audit(
        session,
        actor,
        f"account.{transition}",
        account,
        source_ip,
        {"previous_status": old_status, "status": account.status},
    )
    session.commit()
    return require_account(session, account.id)


def update_account_limits(
    session: Session,
    account_id: UUID,
    payload: AccountLimitsUpdate,
    actor: User,
    source_ip: str | None,
) -> BankAccount:
    if not has_role(actor, ACCOUNT_APPROVER_ROLES):
        raise HTTPException(status_code=403, detail="Account manager role required.")
    account = require_account(session, account_id, lock=True)
    if account.status == "closed":
        raise HTTPException(status_code=409, detail="Closed accounts cannot be changed.")
    account.daily_limit = payload.daily_limit
    account.monthly_limit = payload.monthly_limit
    write_account_audit(
        session,
        actor,
        "account.limits_update",
        account,
        source_ip,
        {
            "daily_limit": str(payload.daily_limit),
            "monthly_limit": str(payload.monthly_limit),
        },
    )
    session.commit()
    return require_account(session, account.id)


def account_balance(account: BankAccount) -> AccountBalanceResponse:
    return AccountBalanceResponse(
        account_id=account.id,
        currency=account.currency,
        current_balance=account.current_balance,
        available_balance=account.current_balance + account.overdraft_limit,
        status=account.status,
    )


def account_statement(
    session: Session,
    account: BankAccount,
    *,
    start_at: datetime | None,
    end_at: datetime | None,
    offset: int,
    limit: int,
) -> AccountStatementResponse:
    rows = get_statement_entries(
        session,
        account.id,
        start_at=start_at,
        end_at=end_at,
        offset=offset,
        limit=limit,
    )
    entries = [
        AccountStatementItem(
            transaction_id=entry.transaction_id,
            reference=transaction.reference,
            transaction_type=transaction.transaction_type,
            direction=entry.entry_type,
            amount=entry.amount,
            balance_after=entry.balance_after,
            currency=account.currency,
            status=transaction.status,
            description=transaction.description,
            created_at=entry.created_at,
        )
        for entry, transaction in rows
    ]
    opening = account.current_balance
    if entries:
        oldest = entries[-1]
        opening = oldest.balance_after + oldest.amount * (
            1 if oldest.direction == "debit" else -1
        )
    closing = entries[0].balance_after if entries else opening
    return AccountStatementResponse(
        account_id=account.id,
        account_number_last4=account.account_number[-4:],
        currency=account.currency,
        opening_balance=opening,
        closing_balance=closing,
        entries=entries,
    )


def search_customer_accounts(
    session: Session,
    *,
    customer_id: UUID | None,
    query: str | None,
    status_filter: str | None,
    account_type: str | None,
    offset: int,
    limit: int,
) -> list[BankAccount]:
    return search_accounts(
        session,
        customer_id=customer_id,
        query=query,
        status=status_filter,
        account_type=account_type,
        offset=offset,
        limit=limit,
    )
