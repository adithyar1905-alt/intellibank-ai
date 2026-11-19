from typing import Literal

from pydantic import BaseModel, Field


class AssistantMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class AssistantResponse(BaseModel):
    intent: Literal["balance", "history", "loan", "education", "mutation_refused"]
    answer: str
    data: dict


class AssistantHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str
