from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


CustomerStatus = Literal["active", "inactive", "blocked"]
KYCDocumentStatus = Literal["pending", "verified", "rejected", "expired"]


def _clean_name(value: str | None) -> str:
    if value is None:
        raise ValueError("Name fields cannot be null.")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Name fields cannot be blank.")
    return cleaned


class CustomerCreate(BaseModel):
    user_id: UUID
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    date_of_birth: date | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, value: str) -> str:
        return _clean_name(value)

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: date | None) -> date | None:
        if value is not None and value >= date.today():
            raise ValueError("Date of birth must be in the past.")
        return value


class CustomerUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    date_of_birth: date | None = None
    email: EmailStr | None = None
    phone_number: str | None = Field(default=None, min_length=7, max_length=32)

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Name fields cannot be null.")
        return _clean_name(value)

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: date | None) -> date | None:
        if value is not None and value >= date.today():
            raise ValueError("Date of birth must be in the past.")
        return value

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Email cannot be null.")
        return value.strip().lower()

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Phone number cannot be blank.")
        return cleaned

    @model_validator(mode="after")
    def require_update_fields(self) -> "CustomerUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one customer field must be provided.")
        return self


class CustomerStatusUpdate(BaseModel):
    status: CustomerStatus


class CustomerResponse(BaseModel):
    id: UUID
    user_id: UUID
    customer_number: str
    first_name: str
    last_name: str
    date_of_birth: date | None
    status: CustomerStatus
    email: str
    phone_number: str | None
    created_at: datetime
    updated_at: datetime


class KYCDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_type: str
    document_number_last4: str | None
    status: KYCDocumentStatus
    expires_at: datetime | None
    verified_at: datetime | None
    created_at: datetime


class CustomerProfileResponse(CustomerResponse):
    kyc_status: Literal["not_submitted", "pending", "verified", "rejected", "expired"]
    kyc_documents: list[KYCDocumentResponse]


class KYCVerificationUpdate(BaseModel):
    status: Literal["verified", "rejected", "expired"]


class KYCUploadResponse(KYCDocumentResponse):
    pass


class AccountHistoryItem(BaseModel):
    transaction_id: UUID
    account_id: UUID
    account_number_last4: str
    reference: str
    transaction_type: str
    amount: str
    currency: str
    status: str
    description: str | None
    created_at: datetime


class RiskAlertSummary(BaseModel):
    id: UUID
    score: float
    severity: str
    status: str
    created_at: datetime


class CustomerRiskProfile(BaseModel):
    customer_id: UUID
    risk_level: Literal["low", "medium", "high", "critical"]
    risk_score: float
    open_alert_count: int
    alerts: list[RiskAlertSummary]