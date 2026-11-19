from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.ai_services.aml_detection.service import (
    evaluate_transaction,
    get_case,
    list_cases,
    list_rules,
    report_summary,
    update_case,
    upsert_rule,
)
from app.core.authentication import CurrentUser
from app.core.authorization import require_roles
from app.database import get_db
from app.repositories.transaction_repository import get_transaction
from app.schemas.aml import (
    AMLCaseResponse,
    AMLCaseUpdate,
    AMLReportResponse,
    AMLRuleResponse,
    AMLRuleUpdate,
)


router = APIRouter(prefix="/aml", tags=["aml-monitoring"])
DatabaseSession = Annotated[Session, Depends(get_db)]
COMPLIANCE_ROLES = ("Super Admin", "Bank Admin", "Branch Manager", "Risk Analyst")


def _source_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


@router.get(
    "/cases",
    response_model=list[AMLCaseResponse],
    dependencies=[Depends(require_roles(*COMPLIANCE_ROLES))],
)
def cases(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    status: Annotated[str | None, Query(pattern="^(open|investigating|escalated|closed)$")] = None,
) -> list[AMLCaseResponse]:
    return [
        AMLCaseResponse.model_validate(item)
        for item in list_cases(session, offset=offset, limit=limit, status_filter=status)
    ]


@router.get(
    "/cases/{case_id}",
    response_model=AMLCaseResponse,
    dependencies=[Depends(require_roles(*COMPLIANCE_ROLES))],
)
def case_detail(case_id: UUID, session: DatabaseSession) -> AMLCaseResponse:
    case = get_case(session, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="AML case not found.")
    return AMLCaseResponse.model_validate(case)


@router.patch(
    "/cases/{case_id}",
    response_model=AMLCaseResponse,
    dependencies=[Depends(require_roles(*COMPLIANCE_ROLES))],
)
def case_update(
    case_id: UUID,
    payload: AMLCaseUpdate,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> AMLCaseResponse:
    case = get_case(session, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="AML case not found.")
    try:
        updated = update_case(
            session,
            case,
            actor,
            status=payload.status,
            assigned_to=(
                payload.assigned_to
                if "assigned_to" in payload.model_fields_set
                else case.assigned_to
            ),
            resolution=payload.resolution,
            source_ip=_source_ip(request),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return AMLCaseResponse.model_validate(updated)


@router.post(
    "/evaluate/{transaction_id}",
    response_model=list[AMLCaseResponse],
    dependencies=[Depends(require_roles(*COMPLIANCE_ROLES))],
)
def evaluate(
    transaction_id: UUID,
    session: DatabaseSession,
    request: Request,
) -> list[AMLCaseResponse]:
    transaction = get_transaction(session, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    try:
        found = evaluate_transaction(session, transaction, _source_ip(request))
        session.commit()
    except (ValueError, RuntimeError) as error:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from error
    return [AMLCaseResponse.model_validate(item) for item in found]


@router.get(
    "/rules",
    response_model=list[AMLRuleResponse],
    dependencies=[Depends(require_roles(*COMPLIANCE_ROLES))],
)
def rules(session: DatabaseSession) -> list[AMLRuleResponse]:
    return [AMLRuleResponse.model_validate(rule) for rule in list_rules(session)]


@router.put(
    "/rules/{code}",
    response_model=AMLRuleResponse,
    dependencies=[Depends(require_roles("Super Admin", "Bank Admin", "Risk Analyst"))],
)
def update_rule(
    code: str,
    payload: AMLRuleUpdate,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> AMLRuleResponse:
    try:
        rule = upsert_rule(
            session,
            code,
            payload.model_dump(),
            actor,
            _source_ip(request),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return AMLRuleResponse.model_validate(rule)


@router.get(
    "/reports/summary",
    response_model=AMLReportResponse,
    dependencies=[Depends(require_roles(*COMPLIANCE_ROLES))],
)
def report(session: DatabaseSession) -> AMLReportResponse:
    return AMLReportResponse.model_validate(report_summary(session))
