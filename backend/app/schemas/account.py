from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


AccountTypeCode = Literal["savings", "current", "fixed_deposit", "recurring_deposit"]


class AccountOpenRequest(BaseModel):
    customer_id: UUID
    account_type: AccountTypeCode
    currency: str = Field(default="USD", pattern=r"^[A-Za-z]{3}$")

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class AccountLimitsUpdate(BaseModel):
    daily_limit: Decimal = Field(gt=0, le=Decimal("1000000000"), max_digits=15, decimal_places=2)
    monthly_limit: Decimal = Field(gt=0, le=Decimal("1000000000"), max_digits=15, decimal_places=2)

    @model_validator(mode="after")
    def limits_consistent(self) -> "AccountLimitsUpdate":
        if self.daily_limit > self.monthly_limit:
            raise ValueError("Daily limit must not exceed monthly limit.")
        return self


class AccountResponse(BaseModel):
    id: UUID
    customer_id: UUID
    account_type: AccountTypeCode
    account_number_last4: str
    currency: str
    current_balance: Decimal
    overdraft_limit: Decimal
    daily_limit: Decimal
    monthly_limit: Decimal
    status: Literal[
        "pending_approval", "pending_activation", "active", "frozen", "closed"
    ]
    approved_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AccountTypeResponse(BaseModel):
    code: AccountTypeCode
    name: str
    minimum_balance: Decimal
    allows_overdraft: bool


class AccountBalanceResponse(BaseModel):
    account_id: UUID
    currency: str
    current_balance: Decimal
    available_balance: Decimal
    status: str


class AccountStatementItem(BaseModel):
    transaction_id: UUID
    reference: str
    transaction_type: str
    direction: Literal["debit", "credit"]
    amount: Decimal
    balance_after: Decimal
    currency: str
    status: str
    description: str | None
    created_at: datetime


class AccountStatementResponse(BaseModel):
    account_id: UUID
    account_number_last4: str
    currency: str
    opening_balance: Decimal
    closing_balance: Decimal
    entries: list[AccountStatementItem]