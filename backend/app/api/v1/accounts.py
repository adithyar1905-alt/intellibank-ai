from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.authentication import CurrentUser
from app.core.authorization import require_roles
from app.database import get_db
from app.models.audit import AuditLog
from app.repositories.account_repository import get_account
from app.schemas.account import (
    AccountBalanceResponse,
    AccountLimitsUpdate,
    AccountOpenRequest,
    AccountResponse,
    AccountStatementResponse,
    AccountTypeResponse,
)
from app.services.account_service import (
    ACCOUNT_APPROVER_ROLES,
    STAFF_ROLES,
    account_balance,
    account_response,
    account_statement,
    has_role,
    list_account_types,
    open_account,
    require_account,
    require_account_access,
    search_customer_accounts,
    transition_account,
    update_account_limits,
)


router = APIRouter(prefix="/accounts", tags=["accounts"])
DatabaseSession = Annotated[Session, Depends(get_db)]

ACCOUNT_STATUS = "^(pending_approval|pending_activation|active|frozen|closed)$"
ACCOUNT_TYPE = "^(savings|current|fixed_deposit|recurring_deposit)$"


def _source_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


def _audit_read(
    session: Session,
    actor: CurrentUser,
    account_id: UUID,
    action: str,
    request: Request,
) -> None:
    session.add(
        AuditLog(
            actor_id=actor.id,
            action=action,
            resource_type="bank_account",
            resource_id=account_id,
            source_ip=_source_ip(request),
            details={},
        )
    )
    session.commit()


@router.get("/types", response_model=list[AccountTypeResponse])
def account_types(session: DatabaseSession) -> list[AccountTypeResponse]:
    return list_account_types(session)


@router.post(
    "",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_account(
    payload: AccountOpenRequest,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> AccountResponse:
    account = open_account(session, payload, actor, _source_ip(request))
    return AccountResponse.model_validate(account_response(account))


@router.get("", response_model=list[AccountResponse])
def search_accounts(
    session: DatabaseSession,
    actor: CurrentUser,
    customer_id: UUID | None = None,
    query: Annotated[str | None, Query(min_length=1, max_length=34)] = None,
    account_status: Annotated[
        str | None, Query(alias="status", pattern=ACCOUNT_STATUS)
    ] = None,
    account_type: Annotated[str | None, Query(pattern=ACCOUNT_TYPE)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> list[AccountResponse]:
    if not has_role(actor, STAFF_ROLES):
        if actor.customer is None:
            raise HTTPException(status_code=403, detail="Customer profile required.")
        if customer_id is not None and customer_id != actor.customer.id:
            raise HTTPException(status_code=403, detail="Account search is not allowed.")
        customer_id = actor.customer.id
    accounts = search_customer_accounts(
        session,
        customer_id=customer_id,
        query=query,
        status_filter=account_status,
        account_type=account_type,
        offset=offset,
        limit=limit,
    )
    return [AccountResponse.model_validate(account_response(item)) for item in accounts]


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(
    account_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> AccountResponse:
    account = require_account(session, account_id)
    require_account_access(account, actor)
    _audit_read(session, actor, account.id, "account.profile_read", request)
    account = require_account(session, account_id)
    return AccountResponse.model_validate(account_response(account))


@router.get("/{account_id}/balance", response_model=AccountBalanceResponse)
def get_balance(
    account_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> AccountBalanceResponse:
    account = require_account(session, account_id)
    require_account_access(account, actor)
    _audit_read(session, actor, account.id, "account.balance_read", request)
    return account_balance(require_account(session, account_id))


@router.get("/{account_id}/statement", response_model=AccountStatementResponse)
def get_statement(
    account_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AccountStatementResponse:
    if start_at is not None and end_at is not None and start_at >= end_at:
        raise HTTPException(
            status_code=422, detail="start_at must be earlier than end_at."
        )
    account = require_account(session, account_id)
    require_account_access(account, actor)
    _audit_read(session, actor, account.id, "account.statement_read", request)
    return account_statement(
        session,
        require_account(session, account_id),
        start_at=start_at,
        end_at=end_at,
        offset=offset,
        limit=limit,
    )


@router.post(
    "/{account_id}/approve",
    response_model=AccountResponse,
    dependencies=[Depends(require_roles(*ACCOUNT_APPROVER_ROLES))],
)
def approve_account(
    account_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> AccountResponse:
    account = transition_account(
        session, account_id, "approve", actor, _source_ip(request)
    )
    return AccountResponse.model_validate(account_response(account))


@router.post(
    "/{account_id}/activate",
    response_model=AccountResponse,
    dependencies=[Depends(require_roles(*STAFF_ROLES))],
)
def activate_account(
    account_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> AccountResponse:
    account = transition_account(
        session, account_id, "activate", actor, _source_ip(request)
    )
    return AccountResponse.model_validate(account_response(account))


@router.post(
    "/{account_id}/freeze",
    response_model=AccountResponse,
    dependencies=[Depends(require_roles(*ACCOUNT_APPROVER_ROLES))],
)
def freeze_account(
    account_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> AccountResponse:
    account = transition_account(
        session, account_id, "freeze", actor, _source_ip(request)
    )
    return AccountResponse.model_validate(account_response(account))


@router.post(
    "/{account_id}/unfreeze",
    response_model=AccountResponse,
    dependencies=[Depends(require_roles(*ACCOUNT_APPROVER_ROLES))],
)
def unfreeze_account(
    account_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> AccountResponse:
    account = transition_account(
        session, account_id, "unfreeze", actor, _source_ip(request)
    )
    return AccountResponse.model_validate(account_response(account))


@router.put(
    "/{account_id}/limits",
    response_model=AccountResponse,
    dependencies=[Depends(require_roles(*ACCOUNT_APPROVER_ROLES))],
)
def set_account_limits(
    account_id: UUID,
    payload: AccountLimitsUpdate,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> AccountResponse:
    account = update_account_limits(
        session, account_id, payload, actor, _source_ip(request)
    )
    return AccountResponse.model_validate(account_response(account))


@router.delete("/{account_id}", response_model=AccountResponse)
def close_account(
    account_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> AccountResponse:
    account = transition_account(
        session, account_id, "close", actor, _source_ip(request)
    )
    return AccountResponse.model_validate(account_response(account))