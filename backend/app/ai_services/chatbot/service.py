"""Ownership-checked, read-only banking assistant orchestration."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.ai_services.chatbot.adapter import AssistantAdapter, get_assistant_adapter
from app.models import AuditLog, BankAccount, Customer, Loan, Transaction, User
from app.models.assistant import AssistantMessage


class BankingAssistantService:
    """Read-only assistant service with PostgreSQL-backed conversation history.

    Rate limiting remains bounded in-process; shared rate limiting is needed for
    deployments with multiple workers.
    """

    def __init__(
        self,
        adapter: AssistantAdapter | None = None,
        *,
        max_requests: int = 20,
        window_seconds: int = 60,
        history_limit: int = 20,
    ) -> None:
        self.adapter = adapter or get_assistant_adapter()
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self.history_limit = history_limit
        self._requests: dict[UUID, deque[datetime]] = defaultdict(deque)
        self._lock = Lock()

    def _customer(self, session: Session, actor: User) -> Customer:
        customer = session.scalar(
            select(Customer).where(
                Customer.user_id == actor.id, Customer.status == "active"
            )
        )
        if customer is None or not actor.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="A verified customer profile is required.",
            )
        return customer

    def _allow(self, user_id: UUID) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            bucket = self._requests[user_id]
            cutoff = now - self.window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Assistant rate limit exceeded.",
                )
            bucket.append(now)

    @staticmethod
    def _audit(session: Session, actor: User, action: str, details: dict) -> None:
        session.add(
            AuditLog(
                actor_id=actor.id,
                action=action,
                resource_type="banking_assistant",
                details=details,
            )
        )
        session.commit()

    def _snapshot(self, session: Session, customer_id: UUID, kind: str) -> dict:
        if kind == "balance":
            accounts = session.scalars(
                select(BankAccount).where(BankAccount.customer_id == customer_id)
            ).all()
            return {
                "accounts": [
                    {
                        "account_id": str(account.id),
                        "account_number_last4": account.account_number[-4:],
                        "currency": account.currency,
                        "balance": str(account.current_balance),
                        "status": account.status,
                    }
                    for account in accounts
                ]
            }
        if kind == "history":
            owned_accounts = select(BankAccount.id).where(
                BankAccount.customer_id == customer_id
            )
            rows = session.scalars(
                select(Transaction)
                .where(
                    or_(
                        Transaction.account_id.in_(owned_accounts),
                        Transaction.related_account_id.in_(owned_accounts),
                    )
                )
                .order_by(Transaction.created_at.desc())
                .limit(50)
            ).all()
            return {
                "transactions": [
                    {
                        "id": str(row.id),
                        "account_id": str(row.account_id),
                        "type": row.transaction_type,
                        "amount": str(row.amount),
                        "currency": row.currency,
                        "status": row.status,
                        "created_at": row.created_at.isoformat(),
                        "description": row.description,
                    }
                    for row in rows
                ]
            }
        loans = session.scalars(
            select(Loan).where(Loan.customer_id == customer_id).order_by(Loan.created_at.desc())
        ).all()
        return {
            "loans": [
                {
                    "id": str(loan.id),
                    "type": loan.loan_type,
                    "principal": str(loan.principal),
                    "outstanding_balance": str(loan.outstanding_balance),
                    "currency": loan.currency,
                    "status": loan.status,
                }
                for loan in loans
            ]
        }

    def respond(self, session: Session, actor: User, message: str) -> tuple[str, str, dict]:
        customer = self._customer(session, actor)
        self._allow(actor.id)
        normalized = message.casefold()
        if any(word in normalized for word in ("transfer", "pay ", "withdraw", "deposit", "send money")):
            answer = "I can only provide information. I cannot execute or initiate transactions."
            intent = "mutation_refused"
            data: dict = {}
        elif any(word in normalized for word in ("balance", "account")):
            intent, data = "balance", self._snapshot(session, customer.id, "balance")
            answer = "Here is your current account information."
        elif any(word in normalized for word in ("transaction", "history", "statement")):
            intent, data = "history", self._snapshot(session, customer.id, "history")
            answer = "Here is your recent transaction history."
        elif "loan" in normalized:
            intent, data = "loan", self._snapshot(session, customer.id, "loan")
            answer = "Here is your loan information."
        else:
            intent, data = "education", {}
            answer = self.adapter.answer(message)
        self._audit(session, actor, "assistant.query", {"intent": intent})
        message_time = datetime.now(timezone.utc)
        session.add_all(
            [
                AssistantMessage(
                    user_id=actor.id,
                    customer_id=customer.id,
                    role="user",
                    content=message,
                    created_at=message_time,
                ),
                AssistantMessage(
                    user_id=actor.id,
                    customer_id=customer.id,
                    role="assistant",
                    content=answer,
                    created_at=message_time + timedelta(microseconds=1),
                ),
            ]
        )
        session.commit()
        retained = session.scalars(
            select(AssistantMessage.id)
            .where(
                AssistantMessage.user_id == actor.id,
                AssistantMessage.customer_id == customer.id,
            )
            .order_by(AssistantMessage.created_at.desc(), AssistantMessage.id.desc())
            .offset(self.history_limit * 2)
        ).all()
        if retained:
            session.execute(
                delete(AssistantMessage).where(AssistantMessage.id.in_(retained))
            )
            session.commit()
        return intent, answer, data

    def history(self, session: Session, actor: User) -> list[dict[str, str]]:
        customer = self._customer(session, actor)
        rows = session.scalars(
            select(AssistantMessage)
            .where(
                AssistantMessage.user_id == actor.id,
                AssistantMessage.customer_id == customer.id,
            )
            .order_by(AssistantMessage.created_at.asc())
            .limit(self.history_limit * 2)
        ).all()
        return [{"role": row.role, "content": row.content} for row in rows]
