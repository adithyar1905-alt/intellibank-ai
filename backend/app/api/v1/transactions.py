from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.authentication import CurrentUser
from app.core.authorization import require_roles
from app.database import get_db
from app.models.audit import AuditLog
from app.models.transaction import Transaction
from app.repositories.account_repository import get_account
from app.repositories.transaction_repository import get_transaction
from app.schemas.transaction import (
    DailyTransactionSummary,
    TransactionCreate,
    TransactionReceipt,
    TransactionResponse,
)
from app.services.account_service import (
    ACCOUNT_APPROVER_ROLES,
    require_account,
    require_account_access,
)
from app.services.transaction_service import (
    create_transaction,
    daily_account_summary,
    require_transaction_access,
    reverse_transaction,
    settle_transaction,
    transaction_history,
    transaction_receipt,
)


router = APIRouter(prefix="/transactions", tags=["transactions"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _source_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


def _check_transaction_access(
    session: Session, transaction: Transaction, actor: CurrentUser
) -> None:
    try:
        require_transaction_access(session, transaction, actor)
        return
    except HTTPException as error:
        if error.status_code != 403 or transaction.related_account_id is None:
            raise
    destination = get_account(session, transaction.related_account_id)
    if destination is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    require_account_access(destination, actor)


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create(
    payload: TransactionCreate,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=8, max_length=128)
    ],
) -> TransactionResponse:
    transaction = create_transaction(
        session, payload, actor, idempotency_key, _source_ip(request)
    )
    return TransactionResponse.model_validate(transaction)


@router.get("", response_model=list[TransactionResponse])
def history(
    account_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> list[TransactionResponse]:
    account = require_account(session, account_id)
    require_account_access(account, actor)
    return [
        TransactionResponse.model_validate(item)
        for item in transaction_history(session, account_id, offset=offset, limit=limit)
    ]


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction_detail(
    transaction_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
) -> TransactionResponse:
    transaction = get_transaction(session, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    _check_transaction_access(session, transaction, actor)
    return TransactionResponse.model_validate(transaction)


@router.get("/{transaction_id}/receipt", response_model=TransactionReceipt)
def receipt(
    transaction_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> TransactionReceipt:
    transaction = get_transaction(session, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    _check_transaction_access(session, transaction, actor)
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="transaction.receipt_read",
            resource_type="transaction",
            resource_id=transaction.id,
            source_ip=_source_ip(request),
            details={},
        )
    )
    session.commit()
    return transaction_receipt(session, transaction)


@router.post(
    "/{transaction_id}/settle",
    response_model=TransactionResponse,
    dependencies=[Depends(require_roles(*ACCOUNT_APPROVER_ROLES))],
)
def settle(
    transaction_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> TransactionResponse:
    transaction = settle_transaction(
        session, transaction_id, actor, _source_ip(request)
    )
    return TransactionResponse.model_validate(transaction)


@router.post(
    "/{transaction_id}/reject",
    response_model=TransactionResponse,
    dependencies=[Depends(require_roles(*ACCOUNT_APPROVER_ROLES))],
)
def reject(
    transaction_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> TransactionResponse:
    transaction = settle_transaction(
        session, transaction_id, actor, _source_ip(request), reject=True
    )
    return TransactionResponse.model_validate(transaction)


@router.post(
    "/{transaction_id}/reverse",
    response_model=TransactionResponse,
    dependencies=[
        Depends(require_roles("Super Admin", "Bank Admin", "Branch Manager"))
    ],
)
def reverse(
    transaction_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> TransactionResponse:
    transaction = reverse_transaction(
        session, transaction_id, actor, _source_ip(request)
    )
    return TransactionResponse.model_validate(transaction)


@router.get(
    "/accounts/{account_id}/daily-summary",
    response_model=DailyTransactionSummary,
)
def daily_summary(
    account_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    summary_date: date = Query(alias="date", default_factory=date.today),
) -> DailyTransactionSummary:
    account = require_account(session, account_id)
    require_account_access(account, actor)
    return daily_account_summary(session, account, summary_date)