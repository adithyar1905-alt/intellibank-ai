from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.ai_services.fraud_detection.model import train_model
from app.ai_services.fraud_detection.service import (
    fraud_artifact_path,
    get_alert,
    list_alerts,
    review_alert,
)
from app.core.authentication import CurrentUser
from app.core.authorization import require_roles
from app.database import get_db
from app.models.audit import AuditLog
from app.schemas.fraud import (
    FraudAlertResponse,
    FraudReviewRequest,
    FraudTrainingRequest,
)


router = APIRouter(prefix="/fraud", tags=["fraud-detection"])
DatabaseSession = Annotated[Session, Depends(get_db)]
RISK_ROLES = ("Super Admin", "Bank Admin", "Branch Manager", "Risk Analyst")


def _source_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


@router.get(
    "/alerts",
    response_model=list[FraudAlertResponse],
    dependencies=[Depends(require_roles(*RISK_ROLES))],
)
def alerts(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> list[FraudAlertResponse]:
    return [
        FraudAlertResponse.model_validate(alert)
        for alert in list_alerts(session, offset=offset, limit=limit)
    ]


@router.post(
    "/alerts/{alert_id}/review",
    response_model=FraudAlertResponse,
    dependencies=[Depends(require_roles(*RISK_ROLES))],
)
def review(
    alert_id: UUID,
    payload: FraudReviewRequest,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> FraudAlertResponse:
    alert = get_alert(session, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Fraud alert not found.")
    try:
        return FraudAlertResponse.model_validate(
            review_alert(
                session,
                alert,
                actor,
                decision=payload.decision,
                notes=payload.notes,
                source_ip=_source_ip(request),
            )
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post(
    "/model/train",
    dependencies=[Depends(require_roles("Super Admin", "Bank Admin", "Risk Analyst"))],
)
def train(
    payload: FraudTrainingRequest,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> dict[str, Any]:
    try:
        metrics = train_model(payload.rows, fraud_artifact_path())
    except (ValueError, RuntimeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="fraud.model_trained",
            resource_type="fraud_model",
            resource_id=None,
            source_ip=_source_ip(request),
            details=metrics,
        )
    )
    session.commit()
    return {
        "metrics": metrics,
        "model_limitations": [
            "Training quality depends on representative, authorized, correctly labeled historical data.",
            "A model score is a risk signal, not proof of fraud.",
            "High-risk transactions require human review; the model never freezes an account.",
        ],
    }
