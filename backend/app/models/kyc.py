from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class KYCDocument(TimestampMixin, Base):
    __tablename__ = "kyc_documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'verified', 'rejected', 'expired')",
            name="valid_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    document_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    document_reference: Mapped[str] = mapped_column(String(512), nullable=False)
    document_number_last4: Mapped[str | None] = mapped_column(String(4))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    customer: Mapped[Customer] = relationship(back_populates="kyc_documents")