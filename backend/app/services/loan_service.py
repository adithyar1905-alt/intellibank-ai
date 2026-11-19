from __future__ import annotations

import calendar
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import uuid
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.audit import AuditLog
from app.models.customer import Customer
from app.models.kyc import KYCDocument
from app.models.loan import Loan, LoanApplication, LoanDocument, LoanRepayment
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.account_repository import get_account
from app.schemas.loan import (
    LoanApplicationCreate,
    LoanEligibilityResponse,
)
from app.services.account_service import STAFF_ROLES, has_role
from app.services.customer.document_storage import remove_document, store_document
from app.services.transaction_service import create_loan_transaction


LOAN_OFFICER_ROLES = (
    "Super Admin",
    "Bank Admin",
    "Branch Manager",
    "Loan Officer",
)
RATES = {
    "personal": Decimal("12.5000"),
    "home": Decimal("7.5000"),
    "education": Decimal("8.0000"),
    "vehicle": Decimal("9.0000"),
    "business": Decimal("14.0000"),
}
MAXIMUM_AMOUNTS = {
    "personal": Decimal("1000000"),
    "home": Decimal("50000000"),
    "education": Decimal("5000000"),
    "vehicle": Decimal("10000000"),
    "business": Decimal("25000000"),
}
MAXIMUM_TERMS = {
    "personal": 60,
    "home": 360,
    "education": 120,
    "vehicle": 84,
    "business": 120,
}
MONEY = Decimal("0.0001")


def calculate_emi(
    principal: Decimal, annual_rate_percent: Decimal, term_months: int
) -> Decimal:
    if principal <= 0 or term_months <= 0:
        raise ValueError("Principal and term must be positive.")
    monthly_rate = annual_rate_percent / Decimal("1200")
    if monthly_rate == 0:
        return (principal / term_months).quantize(MONEY, rounding=ROUND_HALF_UP)
    factor = (Decimal("1") + monthly_rate) ** term_months
    payment = principal * monthly_rate * factor / (factor - Decimal("1"))
    return payment.quantize(MONEY, rounding=ROUND_HALF_UP)


def eligibility(
    payload: LoanApplicationCreate,
    *,
    kyc_verified: bool,
    account_active: bool,
) -> LoanEligibilityResponse:
    rate = RATES[payload.loan_type]
    emi = calculate_emi(payload.requested_amount, rate, payload.requested_term_months)
    reasons: list[str] = []
    if not kyc_verified:
        reasons.append("Verified KYC is required.")
    if not account_active:
        reasons.append("An active disbursement account is required.")
    if payload.requested_amount > MAXIMUM_AMOUNTS[payload.loan_type]:
        reasons.append("Requested amount exceeds the product limit.")
    if payload.requested_term_months > MAXIMUM_TERMS[payload.loan_type]:
        reasons.append("Requested term exceeds the product limit.")
    if emi > payload.declared_monthly_income * Decimal("0.40"):
        reasons.append("Estimated EMI exceeds 40% of declared monthly income.")
    return LoanEligibilityResponse(
        eligible=not reasons,
        estimated_emi=emi,
        annual_interest_rate=rate,
        maximum_amount=MAXIMUM_AMOUNTS[payload.loan_type],
        maximum_term_months=MAXIMUM_TERMS[payload.loan_type],
        reasons=reasons,
    )


def _audit(
    session: Session,
    actor: User,
    action: str,
    resource_id: UUID,
    source_ip: str | None,
    details: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_id=actor.id,
            action=action,
            resource_type="loan_application",
            resource_id=resource_id,
            source_ip=source_ip,
            details=details or {},
        )
    )


def _get_application(
    session: Session, application_id: UUID, *, lock: bool = False
) -> LoanApplication:
    statement = (
        select(LoanApplication)
        .options(selectinload(LoanApplication.documents))
        .where(LoanApplication.id == application_id)
    )
    if lock:
        statement = statement.with_for_update()
    application = session.scalar(statement)
    if application is None:
        raise HTTPException(status_code=404, detail="Loan application not found.")
    return application


def _application_access(application: LoanApplication, actor: User) -> None:
    if has_role(actor, (*LOAN_OFFICER_ROLES, "Risk Analyst")):
        return
    if actor.customer is not None and actor.customer.id == application.customer_id:
        return
    raise HTTPException(status_code=403, detail="You are not allowed to access this loan.")


def _kyc_verified(session: Session, customer_id: UUID) -> bool:
    return (
        session.scalar(
            select(KYCDocument.id).where(
                KYCDocument.customer_id == customer_id,
                KYCDocument.status == "verified",
            )
        )
        is not None
    )


def check_eligibility(
    session: Session, payload: LoanApplicationCreate, actor: User
) -> LoanEligibilityResponse:
    customer = session.get(Customer, payload.customer_id)
    account = get_account(session, payload.disbursement_account_id)
    kyc_verified = customer is not None and _kyc_verified(session, customer.id)
    account_active = (
        customer is not None
        and account is not None
        and account.customer_id == customer.id
        and account.status == "active"
    )
    result = eligibility(
        payload, kyc_verified=kyc_verified, account_active=account_active
    )
    if customer is None:
        result.reasons.append("Customer profile was not found.")
        result.eligible = False
    elif not has_role(actor, STAFF_ROLES) and (
        actor.customer is None or actor.customer.id != customer.id
    ):
        raise HTTPException(status_code=403, detail="You are not allowed to apply.")
    elif customer.status != "active":
        result.reasons.append("An active customer is required.")
        result.eligible = False
    return result


def submit_application(
    session: Session,
    payload: LoanApplicationCreate,
    actor: User,
    source_ip: str | None,
) -> LoanApplication:
    result = check_eligibility(session, payload, actor)
    if not result.eligible:
        raise HTTPException(
            status_code=422,
            detail={"message": "Loan application is not eligible.", "reasons": result.reasons},
        )
    account = get_account(session, payload.disbursement_account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Disbursement account not found.")
    if account.currency != "USD":
        raise HTTPException(status_code=422, detail="Only USD loans are supported.")
    application = LoanApplication(
        customer_id=payload.customer_id,
        disbursement_account_id=payload.disbursement_account_id,
        requested_amount=payload.requested_amount,
        declared_monthly_income=payload.declared_monthly_income,
        requested_term_months=payload.requested_term_months,
        loan_type=payload.loan_type,
        status="submitted",
    )
    session.add(application)
    session.flush()
    _audit(
        session,
        actor,
        "loan.application_submit",
        application.id,
        source_ip,
        {"loan_type": application.loan_type, "amount": str(application.requested_amount)},
    )
    session.commit()
    return _get_application(session, application.id)


def list_applications(
    session: Session,
    actor: User,
    *,
    status_filter: str | None,
    offset: int,
    limit: int,
) -> list[LoanApplication]:
    statement = (
        select(LoanApplication)
        .options(selectinload(LoanApplication.documents))
        .order_by(LoanApplication.submitted_at.desc(), LoanApplication.id)
    )
    if not has_role(actor, (*LOAN_OFFICER_ROLES, "Risk Analyst")):
        if actor.customer is None:
            raise HTTPException(status_code=403, detail="Customer profile required.")
        statement = statement.where(LoanApplication.customer_id == actor.customer.id)
    if status_filter:
        statement = statement.where(LoanApplication.status == status_filter)
    return list(session.scalars(statement.offset(offset).limit(limit)).all())


def get_application(
    session: Session, application_id: UUID, actor: User
) -> LoanApplication:
    application = _get_application(session, application_id)
    _application_access(application, actor)
    return application


def review_application(
    session: Session,
    application_id: UUID,
    actor: User,
    source_ip: str | None,
) -> LoanApplication:
    application = _get_application(session, application_id, lock=True)
    if application.status != "submitted":
        raise HTTPException(status_code=409, detail="Only submitted applications can be reviewed.")
    application.status = "under_review"
    application.reviewed_by = actor.id
    application.reviewed_at = datetime.now(timezone.utc)
    _audit(session, actor, "loan.application_review", application.id, source_ip)
    session.commit()
    return _get_application(session, application.id)


def _next_month(value: datetime) -> datetime:
    next_month = value.month + 1
    year = value.year + (1 if next_month > 12 else 0)
    month = 1 if next_month > 12 else next_month
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _create_repayment_schedule(loan: Loan) -> Decimal:
    payment = calculate_emi(loan.principal, loan.interest_rate, loan.term_months)
    remaining = loan.principal
    due_at = _next_month(datetime.now(timezone.utc))
    for index in range(loan.term_months):
        interest_amount = (
            remaining * loan.interest_rate / Decimal("1200")
        ).quantize(MONEY, rounding=ROUND_HALF_UP)
        principal_amount = (payment - interest_amount).quantize(
            MONEY, rounding=ROUND_HALF_UP
        )
        if index == loan.term_months - 1 or principal_amount >= remaining:
            principal_amount = remaining
        amount = principal_amount + interest_amount
        loan.repayments.append(
            LoanRepayment(
                amount=amount,
                principal_amount=principal_amount,
                interest_amount=interest_amount,
                due_at=due_at,
                status="scheduled",
            )
        )
        remaining -= principal_amount
        due_at = _next_month(due_at)
    return payment


def approve_application(
    session: Session,
    application_id: UUID,
    actor: User,
    source_ip: str | None,
) -> Loan:
    application = _get_application(session, application_id, lock=True)
    if application.status != "under_review":
        raise HTTPException(
            status_code=409, detail="Loan application must be under review before approval."
        )
    if not application.documents:
        raise HTTPException(
            status_code=409, detail="At least one supporting document is required."
        )
    account = get_account(session, application.disbursement_account_id)
    if account is None or account.status != "active":
        raise HTTPException(status_code=409, detail="An active disbursement account is required.")
    if account.customer_id != application.customer_id:
        raise HTTPException(status_code=409, detail="Disbursement account ownership mismatch.")
    if not _kyc_verified(session, application.customer_id):
        raise HTTPException(status_code=409, detail="Verified KYC is required for approval.")

    rate = RATES[application.loan_type]
    loan = Loan(
        customer_id=application.customer_id,
        account_id=account.id,
        principal=application.requested_amount,
        interest_rate=rate,
        term_months=application.requested_term_months,
        currency=account.currency,
        status="active",
        loan_type=application.loan_type,
        outstanding_balance=application.requested_amount,
    )
    _create_repayment_schedule(loan)
    session.add(loan)
    session.flush()
    application.loan_id = loan.id
    application.status = "disbursed"
    application.reviewed_by = actor.id
    application.reviewed_at = datetime.now(timezone.utc)
    transaction = create_loan_transaction(
        session,
        account.id,
        loan.principal,
        actor,
        transaction_type="loan_disbursement",
        description=f"Loan disbursement {loan.id}",
        source_ip=source_ip,
    )
    _audit(
        session,
        actor,
        "loan.application_approve",
        application.id,
        source_ip,
        {"loan_id": str(loan.id), "transaction_id": str(transaction.id)},
    )
    session.commit()
    return session.get(Loan, loan.id)


def reject_application(
    session: Session,
    application_id: UUID,
    reason: str,
    actor: User,
    source_ip: str | None,
) -> LoanApplication:
    application = _get_application(session, application_id, lock=True)
    if application.status not in {"submitted", "under_review"}:
        raise HTTPException(status_code=409, detail="This application cannot be rejected.")
    application.status = "rejected"
    application.rejection_reason = reason.strip()
    application.reviewed_by = actor.id
    application.reviewed_at = datetime.now(timezone.utc)
    _audit(
        session,
        actor,
        "loan.application_reject",
        application.id,
        source_ip,
        {"reason": application.rejection_reason},
    )
    session.commit()
    return _get_application(session, application.id)


def withdraw_application(
    session: Session,
    application_id: UUID,
    actor: User,
    source_ip: str | None,
) -> LoanApplication:
    application = _get_application(session, application_id, lock=True)
    _application_access(application, actor)
    if application.status not in {"submitted", "under_review"}:
        raise HTTPException(status_code=409, detail="This application cannot be withdrawn.")
    application.status = "withdrawn"
    _audit(session, actor, "loan.application_withdraw", application.id, source_ip)
    session.commit()
    return _get_application(session, application.id)


def upload_loan_document(
    session: Session,
    application_id: UUID,
    actor: User,
    *,
    document_type: str,
    content: bytes,
    extension: str,
    source_ip: str | None,
) -> LoanDocument:
    application = _get_application(session, application_id, lock=True)
    _application_access(application, actor)
    if application.status != "submitted":
        raise HTTPException(
            status_code=409, detail="Documents can only be added to submitted applications."
        )
    document_id = uuid.uuid4()
    reference = store_document(
        application.customer_id, document_id, content, extension
    )
    document = LoanDocument(
        id=document_id,
        application_id=application.id,
        document_type=document_type,
        document_reference=reference,
    )
    session.add(document)
    _audit(
        session,
        actor,
        "loan.document_upload",
        application.id,
        source_ip,
        {"document_id": str(document_id), "document_type": document_type},
    )
    committed = False
    try:
        session.commit()
        committed = True
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Unable to save loan document.") from None
    finally:
        if not committed:
            remove_document(reference)
    session.refresh(document)
    return document


def get_loan_document(
    session: Session, application_id: UUID, document_id: UUID, actor: User
) -> LoanDocument:
    application = _get_application(session, application_id)
    _application_access(application, actor)
    document = session.scalar(
        select(LoanDocument).where(
            LoanDocument.id == document_id,
            LoanDocument.application_id == application_id,
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Loan document not found.")
    return document


def loan_details(session: Session, loan_id: UUID, actor: User) -> Loan:
    loan = session.scalar(
        select(Loan)
        .options(selectinload(Loan.repayments))
        .where(Loan.id == loan_id)
    )
    if loan is None:
        raise HTTPException(status_code=404, detail="Loan not found.")
    if not has_role(actor, (*LOAN_OFFICER_ROLES, *STAFF_ROLES)) and (
        actor.customer is None or actor.customer.id != loan.customer_id
    ):
        raise HTTPException(status_code=403, detail="You are not allowed to access this loan.")
    return loan


def pay_repayment(
    session: Session,
    loan_id: UUID,
    repayment_id: UUID,
    account_id: UUID,
    actor: User,
    idempotency_key: str,
    source_ip: str | None,
) -> LoanRepayment:
    loan = session.scalar(
        select(Loan).where(Loan.id == loan_id).with_for_update()
    )
    if loan is None:
        raise HTTPException(status_code=404, detail="Loan not found.")
    if not has_role(actor, STAFF_ROLES) and (
        actor.customer is None or actor.customer.id != loan.customer_id
    ):
        raise HTTPException(status_code=403, detail="You are not allowed to repay this loan.")
    request_data = {
        "loan_id": str(loan_id),
        "repayment_id": str(repayment_id),
        "account_id": str(account_id),
    }
    request_hash = hashlib.sha256(
        json.dumps(request_data, sort_keys=True).encode("utf-8")
    ).hexdigest()
    scoped_key = f"loan:{idempotency_key}"
    existing = session.scalar(
        select(Transaction).where(Transaction.idempotency_key == scoped_key)
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise HTTPException(
                status_code=409,
                detail="Idempotency key was already used for a different loan payment.",
            )
        repayment = session.scalar(
            select(LoanRepayment).where(LoanRepayment.transaction_id == existing.id)
        )
        if repayment is not None:
            return repayment
        raise HTTPException(status_code=409, detail="Loan payment is already being processed.")

    if loan.status != "active":
        raise HTTPException(status_code=409, detail="Loan is not active.")
    repayment = session.scalar(
        select(LoanRepayment)
        .where(
            LoanRepayment.id == repayment_id,
            LoanRepayment.loan_id == loan_id,
        )
        .with_for_update()
    )
    if repayment is None:
        raise HTTPException(status_code=404, detail="Repayment schedule item not found.")
    if repayment.status != "scheduled":
        raise HTTPException(status_code=409, detail="Repayment is not payable.")
    account = get_account(session, account_id, lock=True)
    if account is None or account.customer_id != loan.customer_id:
        raise HTTPException(status_code=403, detail="Payment account ownership mismatch.")
    transaction = create_loan_transaction(
        session,
        account_id,
        repayment.amount,
        actor,
        transaction_type="loan_repayment",
        description=f"Loan repayment {loan.id}",
        source_ip=source_ip,
        idempotency_key=scoped_key,
        request_hash=request_hash,
    )
    repayment.transaction_id = transaction.id
    repayment.paid_at = datetime.now(timezone.utc)
    repayment.status = "paid"
    loan.outstanding_balance = max(
        Decimal("0"), loan.outstanding_balance - repayment.principal_amount
    )
    if loan.outstanding_balance == 0:
        loan.status = "paid_off"
    _audit(
        session,
        actor,
        "loan.repayment",
        loan.id,
        source_ip,
        {
            "repayment_id": str(repayment.id),
            "transaction_id": str(transaction.id),
            "amount": str(repayment.amount),
        },
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="Loan repayment conflicted with another request."
        ) from None
    session.refresh(repayment)
    return repayment
