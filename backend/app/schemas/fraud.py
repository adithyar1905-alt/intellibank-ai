from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FraudAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    transaction_id: UUID | None
    score: Decimal
    severity: str
    status: str
    description: str
    details: dict[str, Any] | None
    created_at: datetime


class FraudReviewRequest(BaseModel):
    decision: Literal["approve", "reject", "investigate"]
    notes: str | None = Field(default=None, max_length=1000)


class FraudTrainingRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(min_length=8, max_length=100_000)
