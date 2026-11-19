from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


AMLStatus = Literal["open", "investigating", "escalated", "closed"]
AMLSeverity = Literal["low", "medium", "high", "critical"]


class AMLCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_number: str
    customer_id: UUID
    transaction_id: UUID
    rule_code: str
    severity: AMLSeverity
    status: AMLStatus
    findings: dict[str, Any]
    assigned_to: UUID | None
    resolution: str | None
    closed_at: datetime | None
    created_at: datetime


class AMLCaseUpdate(BaseModel):
    status: Literal["investigating", "escalated", "closed"]
    assigned_to: UUID | None = None
    resolution: str | None = Field(default=None, max_length=2000)


class AMLRuleUpdate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    enabled: bool
    parameters: dict[str, Any] = Field(default_factory=dict)


class AMLRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    description: str
    enabled: bool
    parameters: dict[str, Any]


class AMLReportResponse(BaseModel):
    total_cases: int
    by_status: dict[str, int]
    by_severity: dict[str, int]
