from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CreditScoreRequest(BaseModel):
    """Applicant-declared inputs; no credit history is inferred or loaded."""

    customer_id: UUID
    monthly_income: Decimal = Field(gt=0, max_digits=17, decimal_places=2)
    monthly_debt: Decimal = Field(ge=0, max_digits=17, decimal_places=2)
    requested_amount: Decimal = Field(gt=0, max_digits=17, decimal_places=2)
    requested_term_months: int = Field(ge=1, le=360)


class FeatureExplanation(BaseModel):
    name: str
    value: Decimal
    contribution: Decimal
    explanation: str


class CreditScoreResponse(BaseModel):
    customer_id: UUID
    score: int = Field(ge=0, le=1000)
    band: Literal["very_high", "high", "moderate", "low", "very_low"]
    probability_of_repayment: float = Field(ge=0, le=1)
    indicative_only: bool = True
    human_review_required: bool = True
    limitations: list[str]
    explanations: list[FeatureExplanation]
    model_version: str


class TrainingMetrics(BaseModel):
    model_version: str
    rows: int = Field(ge=1)
    held_out_rows: int = Field(ge=1)
    accuracy: float = Field(ge=0, le=1)
    roc_auc: float | None = Field(default=None, ge=0, le=1)

