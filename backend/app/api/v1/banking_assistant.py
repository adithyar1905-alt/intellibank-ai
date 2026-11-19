from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai_services.chatbot.service import BankingAssistantService
from app.core.authentication import CurrentUser
from app.core.authorization import require_roles
from app.database import get_db
from app.schemas.banking_assistant import (
    AssistantHistoryItem,
    AssistantMessageRequest,
    AssistantResponse,
)


router = APIRouter(
    prefix="/banking-assistant",
    tags=["banking-assistant"],
    dependencies=[Depends(require_roles("Customer"))],
)
DatabaseSession = Annotated[Session, Depends(get_db)]
_service = BankingAssistantService()


@router.post("/chat", response_model=AssistantResponse)
def chat(
    payload: AssistantMessageRequest,
    session: DatabaseSession,
    actor: CurrentUser,
) -> AssistantResponse:
    """Read-only assistant endpoint; request is validated and never a tool call."""
    message = payload.message.strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="message cannot be blank.",
        )
    intent, answer, data = _service.respond(session, actor, message)
    return AssistantResponse(intent=intent, answer=answer, data=data)


@router.get("/history", response_model=list[AssistantHistoryItem])
def conversation_history(
    session: DatabaseSession, actor: CurrentUser
) -> list[AssistantHistoryItem]:
    return [
        AssistantHistoryItem.model_validate(item)
        for item in _service.history(session, actor)
    ]
