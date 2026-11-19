from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.ai_services.credit_scoring import score_applicant
from app.core.authentication import CurrentUser
from app.core.authorization import require_roles
from app.config import get_settings
from app.database import get_db
from app.models.audit import AuditLog
from app.models.customer import Customer
from app.models.user import User
from app.schemas.credit_scoring import CreditScoreRequest, CreditScoreResponse

router = APIRouter(prefix="/credit-scoring", tags=["credit-scoring"])
DatabaseSession = Annotated[Session, Depends(get_db)]
STAFF_ROLES = ("Super Admin", "Bank Admin", "Branch Manager", "Bank Employee", "Risk Analyst", "Loan Officer")


def _can_access(customer: Customer, user: User) -> bool:
    roles = {role.name for role in user.roles}
    return (
        "Super Admin" in roles
        or bool(roles.intersection(STAFF_ROLES))
        or ("Customer" in roles and customer.user_id == user.id)
    )


@router.post(
    "/score",
    response_model=CreditScoreResponse,
    dependencies=[Depends(require_roles("Customer", *STAFF_ROLES))],
)
def score(
    payload: CreditScoreRequest,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> CreditScoreResponse:
    customer = session.get(Customer, payload.customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    if not _can_access(customer, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not allowed to score this customer.")
    try:
        result = score_applicant(payload, model_path=get_settings().credit_model_path)
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="credit_scoring.prediction",
            resource_type="customer",
            resource_id=customer.id,
            source_ip=request.client.host if request.client else None,
            details={"model_version": result.model_version, "indicative_only": True},
        )
    )
    session.commit()
    return result
