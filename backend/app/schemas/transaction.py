from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


TransactionType = Literal[
    "deposit", "withdrawal", "transfer", "neft", "rtgs", "imps", "upi"
]
TransactionStatus = Literal[
    "pending", "completed", "failed", "reversed", "rejected", "review_required"
]


class TransactionCreate(BaseModel):
    account_id: UUID
    related_account_id: UUID | None = None
    transaction_type: TransactionType
    amount: Decimal = Field(gt=0, max_digits=17, decimal_places=4)
    counterparty_reference: str | None = Field(default=None, min_length=4, max_length=64)
    description: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_route(self) -> "TransactionCreate":
        if self.transaction_type == "transfer":
            if self.related_account_id is None:
                raise ValueError("Internal transfers require a destination account.")
            if self.related_account_id == self.account_id:
                raise ValueError("Source and destination accounts must differ.")
        elif self.transaction_type in {"neft", "rtgs", "imps", "upi"}:
            if not self.counterparty_reference:
                raise ValueError("External payments require a beneficiary reference.")
            if self.related_account_id is not None:
                raise ValueError("External payments cannot specify an internal account.")
        elif self.related_account_id is not None:
            raise ValueError("Only internal transfers may specify a destination account.")
        return self


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reference: str
    account_id: UUID
    related_account_id: UUID | None
    transaction_type: str
    amount: Decimal
    currency: str
    status: TransactionStatus
    description: str | None
    created_at: datetime


class TransactionReceipt(BaseModel):
    reference: str
    transaction_type: str
    amount: Decimal
    currency: str
    status: TransactionStatus
    source_account_last4: str
    destination_account_last4: str | None
    created_at: datetime


class DailyTransactionSummary(BaseModel):
    date: date
    currency: str
    debit_count: int
    debit_total: Decimal
    credit_count: int
    credit_total: Decimal