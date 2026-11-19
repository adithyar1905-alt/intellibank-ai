from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


LoanType = Literal["personal", "home", "education", "vehicle", "business"]
LoanApplicationStatus = Literal[
    "submitted", "under_review", "approved", "rejected", "withdrawn", "disbursed"
]


class LoanApplicationCreate(BaseModel):
    customer_id: UUID
    disbursement_account_id: UUID
    loan_type: LoanType
    requested_amount: Decimal = Field(
        gt=0, max_digits=17, decimal_places=2, le=Decimal("100000000")
    )
    requested_term_months: int = Field(ge=1, le=360)
    declared_monthly_income: Decimal = Field(
        gt=0, max_digits=17, decimal_places=2, le=Decimal("100000000")
    )


class LoanEligibilityResponse(BaseModel):
    eligible: bool
    estimated_emi: Decimal
    annual_interest_rate: Decimal
    maximum_amount: Decimal
    maximum_term_months: int
    reasons: list[str]


class LoanDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_type: str
    created_at: datetime


class LoanApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    disbursement_account_id: UUID | None
    loan_id: UUID | None
    loan_type: LoanType
    requested_amount: Decimal
    requested_term_months: int
    declared_monthly_income: Decimal
    status: LoanApplicationStatus
    rejection_reason: str | None
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    submitted_at: datetime
    documents: list[LoanDocumentResponse]


class LoanReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    loan_type: LoanType
    principal: Decimal
    interest_rate: Decimal
    term_months: int
    currency: str
    status: str
    outstanding_balance: Decimal
    emi_amount: Decimal
    created_at: datetime


class LoanRejectionRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class LoanRepaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    loan_id: UUID
    transaction_id: UUID | None
    amount: Decimal
    principal_amount: Decimal
    interest_amount: Decimal
    due_at: datetime
    paid_at: datetime | None
    status: Literal["scheduled", "paid", "late", "missed"]


class LoanDetailResponse(LoanReviewResponse):
    repayments: list[LoanRepaymentResponse]