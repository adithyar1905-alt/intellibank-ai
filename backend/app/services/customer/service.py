from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import uuid
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.account import BankAccount
from app.models.audit import AuditLog
from app.models.customer import Customer
from app.models.fraud import FraudAlert
from app.models.kyc import KYCDocument
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.customer_repository import (
    get_account_history,
    get_customer,
    get_customer_alerts,
    search_customers,
)
from app.schemas.customer import (
    CustomerCreate,
    CustomerProfileResponse,
    CustomerRiskProfile,
    CustomerUpdate,
    KYCDocumentResponse,
    KYCVerificationUpdate,
)
from app.services.customer.document_storage import (
    remove_document,
    store_document,
)


def _write_audit(
    session: Session,
    actor: User,
    *,
    action: str,
    resource_id: UUID,
    source_ip: str | None,
    details: dict[str, object],
) -> None:
    session.add(
        AuditLog(
            actor_id=actor.id,
            action=action,
            resource_type="customer",
            resource_id=resource_id,
            source_ip=source_ip,
            details=details,
        )
    )


def _require_customer(session: Session, customer_id: UUID) -> Customer:
    customer = get_customer(session, customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found."
        )
    return customer


def _kyc_status(customer: Customer) -> str:
    documents = customer.kyc_documents
    if not documents:
        return "not_submitted"
    statuses = {document.status for document in documents}
    for candidate in ("rejected", "expired", "pending"):
        if candidate in statuses:
            return candidate
    return "verified"


def customer_profile(customer: Customer) -> CustomerProfileResponse:
    return CustomerProfileResponse(
        id=customer.id,
        user_id=customer.user_id,
        customer_number=customer.customer_number,
        first_name=customer.first_name,
        last_name=customer.last_name,
        date_of_birth=customer.date_of_birth,
        status=customer.status,
        email=customer.user.email,
        phone_number=customer.user.phone_number,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
        kyc_status=_kyc_status(customer),
        kyc_documents=[
            KYCDocumentResponse.model_validate(document)
            for document in sorted(
                customer.kyc_documents, key=lambda item: item.created_at, reverse=True
            )
        ],
    )


def create_customer(
    session: Session,
    payload: CustomerCreate,
    actor: User,
    source_ip: str | None,
) -> Customer:
    user = session.get(User, payload.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An inactive user cannot be linked to a new customer.",
        )
    existing = session.scalar(
        select(Customer.id).where(Customer.user_id == payload.user_id)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer profile already exists for this user.",
        )

    customer = Customer(
        user=user,
        customer_number=f"CUST-{uuid.uuid4().hex[:16].upper()}",
        first_name=payload.first_name,
        last_name=payload.last_name,
        date_of_birth=payload.date_of_birth,
        status="active",
    )
    session.add(customer)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer profile already exists for this user.",
        ) from None
    _write_audit(
        session,
        actor,
        action="customer.create",
        resource_id=customer.id,
        source_ip=source_ip,
        details={"user_id": str(user.id), "customer_number": customer.customer_number},
    )
    session.commit()
    return _require_customer(session, customer.id)


def update_customer(
    session: Session,
    customer_id: UUID,
    payload: CustomerUpdate,
    actor: User,
    source_ip: str | None,
) -> Customer:
    customer = _require_customer(session, customer_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if field in {"email", "phone_number"}:
            setattr(customer.user, field, value)
        else:
            setattr(customer, field, value)
    _write_audit(
        session,
        actor,
        action="customer.update",
        resource_id=customer.id,
        source_ip=source_ip,
        details={"updated_fields": sorted(changes)},
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or phone number is already registered.",
        ) from None
    return _require_customer(session, customer.id)


def update_customer_status(
    session: Session,
    customer_id: UUID,
    new_status: str,
    actor: User,
    source_ip: str | None,
) -> Customer:
    customer = _require_customer(session, customer_id)
    old_status = customer.status
    customer.status = new_status
    customer.user.is_active = new_status == "active"
    _write_audit(
        session,
        actor,
        action="customer.status_change",
        resource_id=customer.id,
        source_ip=source_ip,
        details={"previous_status": old_status, "status": new_status},
    )
    session.commit()
    return _require_customer(session, customer.id)


def deactivate_customer(
    session: Session,
    customer_id: UUID,
    actor: User,
    source_ip: str | None,
) -> Customer:
    return update_customer_status(session, customer_id, "inactive", actor, source_ip)


def upload_kyc_document(
    session: Session,
    customer: Customer,
    actor: User,
    *,
    document_type: str,
    content: bytes,
    extension: str,
    document_number_last4: str | None,
    expires_at: datetime | None,
    source_ip: str | None,
) -> KYCDocument:
    document_id = uuid.uuid4()
    reference = store_document(customer.id, document_id, content, extension)
    document = KYCDocument(
        id=document_id,
        customer_id=customer.id,
        document_type=document_type,
        document_reference=reference,
        document_number_last4=document_number_last4,
        status="pending",
        expires_at=expires_at,
    )
    session.add(document)
    _write_audit(
        session,
        actor,
        action="kyc.document_upload",
        resource_id=customer.id,
        source_ip=source_ip,
        details={
            "document_id": str(document_id),
            "document_type": document_type,
        },
    )
    committed = False
    try:
        session.commit()
        committed = True
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to save the KYC document.",
        ) from None
    finally:
        if not committed:
            remove_document(reference)
    session.refresh(document)
    return document


def verify_kyc_document(
    session: Session,
    customer_id: UUID,
    document_id: UUID,
    payload: KYCVerificationUpdate,
    actor: User,
    source_ip: str | None,
) -> KYCDocument:
    _require_customer(session, customer_id)
    document = session.scalar(
        select(KYCDocument).where(
            KYCDocument.id == document_id,
            KYCDocument.customer_id == customer_id,
        )
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC document not found.",
        )
    if document.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending KYC documents can be reviewed.",
        )
    expires_at = document.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if payload.status == "expired" and (
        expires_at is None or expires_at > datetime.now(timezone.utc)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only documents past their expiry date can be marked expired.",
        )
    document.status = payload.status
    document.verified_at = (
        datetime.now(timezone.utc) if payload.status == "verified" else None
    )
    _write_audit(
        session,
        actor,
        action="kyc.document_review",
        resource_id=customer_id,
        source_ip=source_ip,
        details={
            "document_id": str(document.id),
            "status": document.status,
        },
    )
    session.commit()
    session.refresh(document)
    return document


def get_customer_document(
    session: Session, customer_id: UUID, document_id: UUID
) -> KYCDocument:
    _require_customer(session, customer_id)
    document = session.scalar(
        select(KYCDocument).where(
            KYCDocument.id == document_id,
            KYCDocument.customer_id == customer_id,
        )
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC document not found.",
        )
    return document


def audit_document_download(
    session: Session,
    customer_id: UUID,
    document_id: UUID,
    actor: User,
    source_ip: str | None,
) -> None:
    _write_audit(
        session,
        actor,
        action="kyc.document_download",
        resource_id=customer_id,
        source_ip=source_ip,
        details={"document_id": str(document_id)},
    )
    session.commit()


def account_history(
    session: Session, customer_id: UUID, *, offset: int, limit: int
) -> list[tuple[Transaction, BankAccount]]:
    _require_customer(session, customer_id)
    return get_account_history(session, customer_id, offset=offset, limit=limit)


def customer_risk_profile(
    session: Session, customer_id: UUID
) -> CustomerRiskProfile:
    _require_customer(session, customer_id)
    alerts = get_customer_alerts(session, customer_id)
    open_alerts = [
        alert for alert in alerts if alert.status not in {"dismissed", "resolved"}
    ]
    risk_score = max(
        (float(alert.score) for alert in open_alerts),
        default=0.0,
    )
    if any(alert.severity == "critical" for alert in open_alerts):
        risk_level = "critical"
    elif any(alert.severity == "high" for alert in open_alerts) or risk_score >= 0.7:
        risk_level = "high"
    elif any(alert.severity == "medium" for alert in open_alerts) or risk_score >= 0.35:
        risk_level = "medium"
    else:
        risk_level = "low"
    return CustomerRiskProfile(
        customer_id=customer_id,
        risk_level=risk_level,
        risk_score=risk_score,
        open_alert_count=len(open_alerts),
        alerts=[
            {
                "id": alert.id,
                "score": float(alert.score),
                "severity": alert.severity,
                "status": alert.status,
                "created_at": alert.created_at,
            }
            for alert in alerts[:10]
        ],
    )


def find_customers(
    session: Session,
    *,
    query: str | None,
    status_filter: str | None,
    offset: int,
    limit: int,
) -> list[Customer]:
    return search_customers(
        session,
        query=query,
        status=status_filter,
        offset=offset,
        limit=limit,
    )


def decimal_amount(value: Decimal) -> str:
    return format(value, "f")
