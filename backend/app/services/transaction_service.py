from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
import secrets
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.account import BankAccount
from app.models.audit import AuditLog
from app.models.ledger import LedgerEntry
from app.models.transaction import Transaction
from app.models.user import User
from app.config import get_settings
from app.ai_services.aml_detection.service import (
    evaluate_transaction as evaluate_aml_transaction,
)
from app.ai_services.fraud_detection.service import (
    evaluate_transaction as evaluate_fraud_transaction,
)
from app.repositories.transaction_repository import (
    daily_outbound_total,
    daily_summary,
    get_transaction,
    get_transaction_for_idempotency,
    list_account_transactions,
    monthly_outbound_total,
)
from app.schemas.transaction import (
    DailyTransactionSummary,
    TransactionCreate,
    TransactionReceipt,
    TransactionResponse,
)
from app.services.account_service import STAFF_ROLES, has_role, require_account_access


EXTERNAL_RAILS = {"neft", "rtgs", "imps", "upi"}
OUTBOUND_TYPES = {"withdrawal", "transfer", *EXTERNAL_RAILS}


def _request_hash(payload: TransactionCreate) -> str:
    data = payload.model_dump(mode="json")
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _audit(
    session: Session,
    actor: User,
    transaction: Transaction,
    action: str,
    source_ip: str | None,
    details: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_id=actor.id,
            action=action,
            resource_type="transaction",
            resource_id=transaction.id,
            source_ip=source_ip,
            details=details or {},
        )
    )


def _load_accounts(
    session: Session, account_ids: set[UUID], *, lock: bool
) -> dict[UUID, BankAccount]:
    statement = (
        select(BankAccount)
        .options(selectinload(BankAccount.account_type))
        .where(BankAccount.id.in_(account_ids))
        .order_by(BankAccount.id)
    )
    if lock:
        statement = statement.with_for_update()
    accounts = {
        account.id: account for account in session.scalars(statement).all()
    }
    if len(accounts) != len(account_ids):
        raise HTTPException(status_code=404, detail="One or more accounts were not found.")
    return accounts


def _check_account_active(account: BankAccount) -> None:
    if account.status != "active":
        raise HTTPException(
            status_code=409, detail="Transactions require active accounts."
        )


def _check_owner(account: BankAccount, actor: User) -> None:
    if has_role(actor, STAFF_ROLES):
        return
    require_account_access(account, actor)


def _check_outbound_rules(
    session: Session, account: BankAccount, amount: Decimal, *, check_limits: bool = True
) -> None:
    _check_account_active(account)
    if account.account_type.code in {"fixed_deposit", "recurring_deposit"}:
        raise HTTPException(
            status_code=409,
            detail="Fixed and recurring deposits do not support outbound transactions.",
        )
    available = account.current_balance + account.overdraft_limit
    minimum = account.account_type.minimum_balance
    if account.current_balance - amount < max(minimum, -account.overdraft_limit):
        raise HTTPException(
            status_code=409,
            detail="Insufficient available balance or account minimum balance would be breached.",
        )
    if check_limits:
        today = datetime.now(timezone.utc).date()
        if daily_outbound_total(session, account.id, today) + amount > account.daily_limit:
            raise HTTPException(status_code=409, detail="Daily transaction limit exceeded.")
        if monthly_outbound_total(session, account.id, today) + amount > account.monthly_limit:
            raise HTTPException(status_code=409, detail="Monthly transaction limit exceeded.")
    if amount > available:
        raise HTTPException(status_code=409, detail="Insufficient available balance.")


def _apply_entry(
    session: Session,
    transaction: Transaction,
    account: BankAccount,
    amount: Decimal,
    entry_type: str,
) -> None:
    if entry_type == "debit":
        new_balance = account.current_balance - amount
        if new_balance < -account.overdraft_limit:
            raise HTTPException(status_code=409, detail="Insufficient available balance.")
        account.current_balance = new_balance
    else:
        account.current_balance += amount
        new_balance = account.current_balance
    session.add(
        LedgerEntry(
            transaction_id=transaction.id,
            account_id=account.id,
            entry_type=entry_type,
            amount=amount,
            balance_after=new_balance,
        )
    )


def _make_transaction(
    session: Session,
    payload: TransactionCreate,
    actor: User,
    *,
    idempotency_key: str | None,
    request_hash: str | None,
    status_value: str,
    transaction_type: str | None = None,
    reversed_transaction_id: UUID | None = None,
) -> Transaction:
    transaction = Transaction(
        reference=f"TXN-{secrets.token_hex(16).upper()}",
        account_id=payload.account_id,
        related_account_id=payload.related_account_id,
        initiated_by=actor.id,
        transaction_type=transaction_type or payload.transaction_type,
        amount=payload.amount,
        currency="USD",
        status=status_value,
        description=payload.description,
        counterparty_reference=payload.counterparty_reference,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        reversed_transaction_id=reversed_transaction_id,
    )
    session.add(transaction)
    session.flush()
    return transaction


def _post_new_transaction(
    session: Session, transaction: Transaction, accounts: dict[UUID, BankAccount]
) -> None:
    source = accounts[transaction.account_id]
    amount = transaction.amount
    if transaction.transaction_type == "deposit" or transaction.transaction_type == "loan_disbursement":
        _check_account_active(source)
        _apply_entry(session, transaction, source, amount, "credit")
    elif transaction.transaction_type == "transfer":
        destination_id = transaction.related_account_id
        if destination_id is None:
            raise HTTPException(status_code=422, detail="Transfer destination is required.")
        destination = accounts[destination_id]
        _check_outbound_rules(session, source, amount)
        _check_account_active(destination)
        if source.currency != destination.currency:
            raise HTTPException(status_code=422, detail="Account currencies must match.")
        _apply_entry(session, transaction, source, amount, "debit")
        _apply_entry(session, transaction, destination, amount, "credit")
    elif transaction.transaction_type in EXTERNAL_RAILS:
        _check_outbound_rules(session, source, amount)
        _apply_entry(session, transaction, source, amount, "debit")
    else:
        _check_outbound_rules(session, source, amount)
        _apply_entry(session, transaction, source, amount, "debit")


def create_transaction(
    session: Session,
    payload: TransactionCreate,
    actor: User,
    idempotency_key: str,
    source_ip: str | None,
) -> Transaction:
    digest = _request_hash(payload)
    existing = get_transaction_for_idempotency(session, idempotency_key)
    if existing is not None:
        existing_account = _load_accounts(
            session, {existing.account_id}, lock=False
        )[existing.account_id]
        _check_owner(existing_account, actor)
        if existing.request_hash != digest:
            raise HTTPException(
                status_code=409,
                detail="Idempotency key was already used for a different request.",
            )
        return existing
    account_ids = {payload.account_id}
    if payload.related_account_id is not None:
        account_ids.add(payload.related_account_id)
    accounts = _load_accounts(session, account_ids, lock=True)
    source = accounts[payload.account_id]
    _check_owner(source, actor)
    if payload.transaction_type == "deposit" and not has_role(actor, STAFF_ROLES):
        raise HTTPException(
            status_code=403, detail="Only bank staff may post cash deposits."
        )
    if payload.transaction_type in OUTBOUND_TYPES:
        _check_outbound_rules(session, source, payload.amount)
    if payload.transaction_type in EXTERNAL_RAILS:
        _check_account_active(source)
        transaction_status = "pending"
    else:
        transaction_status = "completed"
    transaction = _make_transaction(
        session,
        payload,
        actor,
        idempotency_key=idempotency_key,
        request_hash=digest,
        status_value=transaction_status,
    )
    risk_score, _, _ = evaluate_fraud_transaction(
        session, transaction, source, actor, source_ip
    )
    review_required = risk_score >= get_settings().fraud_review_threshold
    if review_required:
        transaction.status = "review_required"
    else:
        _post_new_transaction(session, transaction, accounts)
    evaluate_aml_transaction(session, transaction, source_ip)
    _audit(
        session,
        actor,
        transaction,
        "transaction.create",
        source_ip,
        {
            "status": transaction.status,
            "amount": str(transaction.amount),
            "fraud_review_required": review_required,
        },
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = get_transaction_for_idempotency(session, idempotency_key)
        if existing is None:
            raise HTTPException(
                status_code=409,
                detail="Unable to create transaction due to a conflicting request.",
            ) from None
        if existing.request_hash != digest:
            raise HTTPException(
                status_code=409,
                detail="Idempotency key was already used for a different request.",
            ) from None
        return existing
    return session.get(Transaction, transaction.id)


def approve_fraud_review(
    session: Session,
    transaction: Transaction,
    actor: User,
    source_ip: str | None,
    *,
    reject: bool,
) -> Transaction:
    if transaction.status != "review_required":
        raise HTTPException(
            status_code=409, detail="Transaction is not waiting for fraud review."
        )
    account_ids = {transaction.account_id}
    if transaction.related_account_id is not None:
        account_ids.add(transaction.related_account_id)
    accounts = _load_accounts(session, account_ids, lock=True)
    if reject:
        transaction.status = "rejected"
        action = "transaction.fraud_review_rejected"
    else:
        transaction.status = (
            "pending" if transaction.transaction_type in EXTERNAL_RAILS else "completed"
        )
        _post_new_transaction(session, transaction, accounts)
        action = "transaction.fraud_review_approved"
    _audit(
        session,
        actor,
        transaction,
        action,
        source_ip,
        {"decision": "reject" if reject else "approve"},
    )
    session.flush()
    return transaction


def settle_transaction(
    session: Session,
    transaction_id: UUID,
    actor: User,
    source_ip: str | None,
    *,
    reject: bool = False,
) -> Transaction:
    transaction = get_transaction(session, transaction_id, lock=True)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    if transaction.status != "pending" or transaction.transaction_type not in EXTERNAL_RAILS:
        raise HTTPException(
            status_code=409, detail="Only pending external payments can be settled."
        )
    if reject:
        accounts = _load_accounts(session, {transaction.account_id}, lock=True)
        _apply_entry(
            session,
            transaction,
            accounts[transaction.account_id],
            transaction.amount,
            "credit",
        )
        transaction.status = "rejected"
        action = "transaction.reject"
    else:
        transaction.status = "completed"
        action = "transaction.settle"
    _audit(session, actor, transaction, action, source_ip)
    session.commit()
    return session.get(Transaction, transaction.id)


def reverse_transaction(
    session: Session,
    transaction_id: UUID,
    actor: User,
    source_ip: str | None,
) -> Transaction:
    if not has_role(actor, ("Super Admin", "Bank Admin", "Branch Manager")):
        raise HTTPException(status_code=403, detail="Transaction reversal role required.")
    original = get_transaction(session, transaction_id, lock=True)
    if original is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    if original.status != "completed":
        raise HTTPException(
            status_code=409, detail="Only completed transactions can be reversed."
        )
    if original.transaction_type in {"loan_disbursement", "loan_repayment"}:
        raise HTTPException(
            status_code=409,
            detail="Loan transactions must be reversed through the loan workflow.",
        )
    account_ids = {original.account_id}
    if original.related_account_id is not None:
        account_ids.add(original.related_account_id)
    accounts = _load_accounts(session, account_ids, lock=True)
    reversal_payload = TransactionCreate(
        account_id=original.account_id,
        related_account_id=original.related_account_id,
        transaction_type="transfer" if original.transaction_type == "transfer" else "withdrawal",
        amount=original.amount,
        description=f"Reversal of {original.reference}",
        counterparty_reference=original.counterparty_reference,
    )
    reversal = _make_transaction(
        session,
        reversal_payload,
        actor,
        idempotency_key=None,
        request_hash=None,
        status_value="completed",
        transaction_type="reversal",
        reversed_transaction_id=original.id,
    )
    if original.transaction_type == "transfer":
        destination_id = original.related_account_id
        if destination_id is None:
            raise HTTPException(status_code=409, detail="Transfer destination is missing.")
        destination = accounts[destination_id]
        _apply_entry(session, reversal, destination, original.amount, "debit")
        _apply_entry(session, reversal, accounts[original.account_id], original.amount, "credit")
    elif original.transaction_type == "deposit":
        _apply_entry(session, reversal, accounts[original.account_id], original.amount, "debit")
    else:
        _apply_entry(session, reversal, accounts[original.account_id], original.amount, "credit")
    original.status = "reversed"
    _audit(
        session,
        actor,
        original,
        "transaction.reverse",
        source_ip,
        {"reversal_transaction_id": str(reversal.id)},
    )
    session.commit()
    return session.get(Transaction, reversal.id)


def require_transaction_access(
    session: Session, transaction: Transaction, actor: User
) -> None:
    source = _load_accounts(session, {transaction.account_id}, lock=False)[
        transaction.account_id
    ]
    _check_owner(source, actor)


def transaction_receipt(
    session: Session, transaction: Transaction
) -> TransactionReceipt:
    source = _load_accounts(session, {transaction.account_id}, lock=False)[
        transaction.account_id
    ]
    destination_number = None
    if transaction.related_account_id is not None:
        destination = _load_accounts(
            session, {transaction.related_account_id}, lock=False
        )[transaction.related_account_id]
        destination_number = destination.account_number[-4:]
    return TransactionReceipt(
        reference=transaction.reference,
        transaction_type=transaction.transaction_type,
        amount=transaction.amount,
        currency=transaction.currency,
        status=transaction.status,
        source_account_last4=source.account_number[-4:],
        destination_account_last4=destination_number,
        created_at=transaction.created_at,
    )


def transaction_history(
    session: Session, account_id: UUID, *, offset: int, limit: int
) -> list[Transaction]:
    return list_account_transactions(session, account_id, offset=offset, limit=limit)


def daily_account_summary(
    session: Session, account: BankAccount, day: date
) -> DailyTransactionSummary:
    debits, debit_total, credits, credit_total = daily_summary(
        session, account.id, day
    )
    return DailyTransactionSummary(
        date=day,
        currency=account.currency,
        debit_count=debits,
        debit_total=debit_total,
        credit_count=credits,
        credit_total=credit_total,
    )


def create_loan_transaction(
    session: Session,
    account_id: UUID,
    amount: Decimal,
    actor: User,
    *,
    transaction_type: str,
    description: str,
    source_ip: str | None,
    idempotency_key: str | None = None,
    request_hash: str | None = None,
) -> Transaction:
    accounts = _load_accounts(session, {account_id}, lock=True)
    account = accounts[account_id]
    _check_account_active(account)
    payload = TransactionCreate(
        account_id=account_id,
        transaction_type="withdrawal",
        amount=amount,
        description=description,
    )
    transaction = _make_transaction(
        session,
        payload,
        actor,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        status_value="completed",
        transaction_type=transaction_type,
    )
    if transaction_type == "loan_disbursement":
        _apply_entry(session, transaction, account, amount, "credit")
    elif transaction_type == "loan_repayment":
        _check_outbound_rules(session, account, amount)
        _apply_entry(session, transaction, account, amount, "debit")
    else:
        raise ValueError(f"Unsupported loan transaction type: {transaction_type}")
    _audit(
        session,
        actor,
        transaction,
        f"transaction.{transaction_type}",
        source_ip,
    )
    session.flush()
    return transaction
