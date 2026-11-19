from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from cryptography.fernet import Fernet
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.core.authentication import get_current_user
from app.database import create_database_engine, get_db
from app.main import app
from app.models import (
    AccountType,
    AuditLog,
    Base,
    BankAccount,
    Customer,
    KYCDocument,
    LedgerEntry,
    Loan,
    LoanApplication,
    LoanRepayment,
    Role,
    Transaction,
    User,
)


@pytest.fixture
def banking_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("KYC_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setenv("KYC_STORAGE_PATH", str(tmp_path / "private-documents"))
    get_settings.cache_clear()
    engine = create_database_engine(
        f"sqlite+pysqlite:///{tmp_path / 'banking.db'}"
    )
    Base.metadata.create_all(engine)

    customer_id = uuid4()
    customer_user_id = uuid4()
    staff_user_id = uuid4()
    loan_officer_id = uuid4()
    with Session(engine) as session:
        customer_role = Role(name="Customer")
        staff_role = Role(name="Bank Admin")
        loan_officer_role = Role(name="Loan Officer")
        customer_user = User(
            id=customer_user_id,
            email="bank-customer@example.com",
            password_hash="test-hash",
            roles=[customer_role],
        )
        staff_user = User(
            id=staff_user_id,
            email="bank-admin@example.com",
            password_hash="test-hash",
            roles=[staff_role],
        )
        loan_officer = User(
            id=loan_officer_id,
            email="loan-officer@example.com",
            password_hash="test-hash",
            roles=[loan_officer_role],
        )
        customer = Customer(
            id=customer_id,
            user=customer_user,
            customer_number="CUST-FIN-0001",
            first_name="Ada",
            last_name="Lovelace",
            status="active",
        )
        session.add_all(
            [
                customer,
                staff_user,
                loan_officer,
                AccountType(code="savings", name="Savings Account"),
                AccountType(code="current", name="Current Account"),
                AccountType(code="fixed_deposit", name="Fixed Deposit"),
                AccountType(code="recurring_deposit", name="Recurring Deposit"),
                KYCDocument(
                    customer=customer,
                    document_type="passport",
                    document_reference="private/test/passport.enc",
                    status="verified",
                ),
            ]
        )
        session.commit()

    current_actor = {"id": staff_user_id}

    def override_db():
        with Session(engine) as session:
            yield session

    def override_current_user():
        with Session(engine) as session:
            user = session.scalar(
                select(User)
                .options(selectinload(User.roles), selectinload(User.customer))
                .where(User.id == current_actor["id"])
            )
            assert user is not None
            return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_current_user
    with TestClient(app) as client:
        yield {
            "client": client,
            "engine": engine,
            "customer_id": customer_id,
            "customer_user_id": customer_user_id,
            "staff_user_id": staff_user_id,
            "loan_officer_id": loan_officer_id,
            "current_actor": current_actor,
        }
    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()


def open_active_account(
    banking_api: dict[str, object], *, account_type: str = "savings"
) -> dict[str, object]:
    client = banking_api["client"]
    opened = client.post(
        "/api/v1/accounts",
        json={
            "customer_id": str(banking_api["customer_id"]),
            "account_type": account_type,
            "currency": "USD",
        },
    )
    assert opened.status_code == 201, opened.text
    assert len(opened.json()["account_number_last4"]) == 4
    account_id = opened.json()["id"]
    approved = client.post(f"/api/v1/accounts/{account_id}/approve")
    assert approved.status_code == 200, approved.text
    activated = client.post(f"/api/v1/accounts/{account_id}/activate")
    assert activated.status_code == 200, activated.text
    return activated.json()


def test_account_lifecycle_limits_balance_and_ownership(
    banking_api: dict[str, object],
) -> None:
    api = banking_api
    client = api["client"]
    opened = client.post(
        "/api/v1/accounts",
        json={
            "customer_id": str(api["customer_id"]),
            "account_type": "current",
        },
    )
    assert opened.status_code == 201
    assert opened.json()["status"] == "pending_approval"

    account_id = opened.json()["id"]
    assert client.get(f"/api/v1/accounts/{account_id}/balance").status_code == 200
    assert client.post(f"/api/v1/accounts/{account_id}/activate").status_code == 409
    assert client.post(f"/api/v1/accounts/{account_id}/approve").status_code == 200
    assert client.post(f"/api/v1/accounts/{account_id}/activate").status_code == 200

    limits = client.put(
        f"/api/v1/accounts/{account_id}/limits",
        json={"daily_limit": "500", "monthly_limit": "5000"},
    )
    assert limits.status_code == 200
    assert limits.json()["daily_limit"] == "500.0000"
    invalid_limits = client.put(
        f"/api/v1/accounts/{account_id}/limits",
        json={"daily_limit": "6000", "monthly_limit": "5000"},
    )
    assert invalid_limits.status_code == 422

    assert client.post(f"/api/v1/accounts/{account_id}/freeze").status_code == 200
    assert client.post(f"/api/v1/accounts/{account_id}/unfreeze").status_code == 200
    api["current_actor"]["id"] = api["customer_user_id"]
    assert client.get(f"/api/v1/accounts/{account_id}").status_code == 200
    assert client.get(
        f"/api/v1/accounts/{uuid4()}"
    ).status_code == 404

    with Session(api["engine"]) as session:
        actions = set(
            session.scalars(
                select(AuditLog.action).where(
                    AuditLog.resource_id == UUID(account_id)
                )
            )
        )
    assert {
        "account.open",
        "account.approve",
        "account.activate",
        "account.limits_update",
        "account.freeze",
        "account.unfreeze",
        "account.profile_read",
    }.issubset(actions)


def test_transfer_idempotency_atomic_ledger_and_reversal(
    banking_api: dict[str, object],
) -> None:
    api = banking_api
    client = api["client"]
    source = open_active_account(api)
    destination = open_active_account(api)
    source_id = source["id"]
    destination_id = destination["id"]

    deposit_payload = {
        "account_id": source_id,
        "transaction_type": "deposit",
        "amount": "500.00",
        "description": "Initial funding",
    }
    deposited = client.post(
        "/api/v1/transactions",
        json=deposit_payload,
        headers={"Idempotency-Key": "deposit-key-0001"},
    )
    assert deposited.status_code == 201, deposited.text
    replay = client.post(
        "/api/v1/transactions",
        json=deposit_payload,
        headers={"Idempotency-Key": "deposit-key-0001"},
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == deposited.json()["id"]

    api["current_actor"]["id"] = api["customer_user_id"]
    transfer_payload = {
        "account_id": source_id,
        "related_account_id": destination_id,
        "transaction_type": "transfer",
        "amount": "125.00",
    }
    transfer = client.post(
        "/api/v1/transactions",
        json=transfer_payload,
        headers={"Idempotency-Key": "transfer-key-0001"},
    )
    assert transfer.status_code == 201, transfer.text
    duplicate = client.post(
        "/api/v1/transactions",
        json={**transfer_payload, "amount": "126.00"},
        headers={"Idempotency-Key": "transfer-key-0001"},
    )
    assert duplicate.status_code == 409

    source_balance = client.get(f"/api/v1/accounts/{source_id}/balance").json()
    destination_balance = client.get(
        f"/api/v1/accounts/{destination_id}/balance"
    ).json()
    assert source_balance["current_balance"] == "375.0000"
    assert destination_balance["current_balance"] == "125.0000"

    api["current_actor"]["id"] = api["staff_user_id"]
    reversed_tx = client.post(
        f"/api/v1/transactions/{transfer.json()['id']}/reverse"
    )
    assert reversed_tx.status_code == 200, reversed_tx.text
    assert reversed_tx.json()["transaction_type"] == "reversal"
    assert client.post(
        f"/api/v1/transactions/{transfer.json()['id']}/reverse"
    ).status_code == 409
    assert client.get(f"/api/v1/accounts/{source_id}/balance").json()[
        "current_balance"
    ] == "500.0000"
    assert client.get(f"/api/v1/accounts/{destination_id}/balance").json()[
        "current_balance"
    ] == "0.0000"

    with Session(api["engine"]) as session:
        postings = list(session.scalars(select(LedgerEntry)).all())
        assert len(postings) == 5
        assert len({posting.transaction_id for posting in postings}) == 3
        with pytest.raises(ValueError, match="immutable"):
            postings[0].amount = Decimal("1.0000")
            session.flush()


def test_balance_rules_account_statement_and_daily_summary(
    banking_api: dict[str, object],
) -> None:
    api = banking_api
    client = api["client"]
    account = open_active_account(api)
    account_id = account["id"]
    for key, amount in (("deposit-limit-01", "200.00"),):
        response = client.post(
            "/api/v1/transactions",
            json={
                "account_id": account_id,
                "transaction_type": "deposit",
                "amount": amount,
            },
            headers={"Idempotency-Key": key},
        )
        assert response.status_code == 201, response.text

    api["current_actor"]["id"] = api["customer_user_id"]
    withdrawal = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "transaction_type": "withdrawal",
            "amount": "250.00",
        },
        headers={"Idempotency-Key": "withdrawal-key-001"},
    )
    assert withdrawal.status_code == 409
    assert client.get(f"/api/v1/accounts/{account_id}/balance").json()[
        "current_balance"
    ] == "200.0000"

    api["current_actor"]["id"] = api["staff_user_id"]
    statement = client.get(f"/api/v1/accounts/{account_id}/statement")
    assert statement.status_code == 200
    assert statement.json()["closing_balance"] == "200.0000"
    assert statement.json()["entries"][0]["direction"] == "credit"
    summary = client.get(
        f"/api/v1/transactions/accounts/{account_id}/daily-summary"
    )
    assert summary.status_code == 200
    assert summary.json()["credit_total"] == "200.0000"


def test_external_payment_reserves_balance_until_settlement_or_rejection(
    banking_api: dict[str, object],
) -> None:
    api = banking_api
    client = api["client"]
    account = open_active_account(api)
    account_id = account["id"]
    deposit = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "transaction_type": "deposit",
            "amount": "100.00",
        },
        headers={"Idempotency-Key": "external-fund-001"},
    )
    assert deposit.status_code == 201

    api["current_actor"]["id"] = api["customer_user_id"]
    pending = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "transaction_type": "neft",
            "amount": "75.00",
            "counterparty_reference": "BENEFICIARY-001",
        },
        headers={"Idempotency-Key": "neft-payment-key-1"},
    )
    assert pending.status_code == 201, pending.text
    assert pending.json()["status"] == "pending"
    assert client.get(f"/api/v1/accounts/{account_id}/balance").json()[
        "current_balance"
    ] == "25.0000"
    insufficient = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "transaction_type": "upi",
            "amount": "30.00",
            "counterparty_reference": "VPA-001",
        },
        headers={"Idempotency-Key": "upi-payment-key-01"},
    )
    assert insufficient.status_code == 409

    api["current_actor"]["id"] = api["staff_user_id"]
    rejected = client.post(f"/api/v1/transactions/{pending.json()['id']}/reject")
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert client.get(f"/api/v1/accounts/{account_id}/balance").json()[
        "current_balance"
    ] == "100.0000"

    api["current_actor"]["id"] = api["customer_user_id"]
    another_pending = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "transaction_type": "imps",
            "amount": "40.00",
            "counterparty_reference": "BENEFICIARY-002",
        },
        headers={"Idempotency-Key": "imps-payment-key-01"},
    )
    assert another_pending.status_code == 201
    api["current_actor"]["id"] = api["staff_user_id"]
    settled = client.post(
        f"/api/v1/transactions/{another_pending.json()['id']}/settle"
    )
    assert settled.status_code == 200
    assert settled.json()["status"] == "completed"
    assert client.get(f"/api/v1/accounts/{account_id}/balance").json()[
        "current_balance"
    ] == "60.0000"


def test_loan_application_workflow_disbursement_and_repayment(
    banking_api: dict[str, object],
) -> None:
    api = banking_api
    client = api["client"]
    account = open_active_account(api)
    application_payload = {
        "customer_id": str(api["customer_id"]),
        "disbursement_account_id": account["id"],
        "loan_type": "personal",
        "requested_amount": "12000.00",
        "requested_term_months": 24,
        "declared_monthly_income": "5000.00",
    }
    eligibility = client.post("/api/v1/loans/eligibility", json=application_payload)
    assert eligibility.status_code == 200, eligibility.text
    assert eligibility.json()["eligible"] is True
    application = client.post(
        "/api/v1/loans/applications", json=application_payload
    )
    assert application.status_code == 201, application.text
    application_id = application.json()["id"]

    unsupported = client.post(
        f"/api/v1/loans/applications/{application_id}/documents",
        data={"document_type": "income"},
        files={"file": ("bad.txt", b"not a document", "text/plain")},
    )
    assert unsupported.status_code == 415
    uploaded = client.post(
        f"/api/v1/loans/applications/{application_id}/documents",
        data={"document_type": "income"},
        files={
            "file": (
                "income.pdf",
                b"%PDF-1.7\nproof of income",
                "application/pdf",
            )
        },
    )
    assert uploaded.status_code == 201, uploaded.text
    api["current_actor"]["id"] = api["customer_user_id"]
    reviewed = client.post(
        f"/api/v1/loans/applications/{application_id}/review"
    )
    assert reviewed.status_code == 403

    api["current_actor"]["id"] = api["loan_officer_id"]
    reviewed = client.post(
        f"/api/v1/loans/applications/{application_id}/review"
    )
    assert reviewed.status_code == 200, reviewed.text
    approved = client.post(
        f"/api/v1/loans/applications/{application_id}/approve"
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "active"
    loan_id = approved.json()["id"]
    assert approved.json()["outstanding_balance"] == "12000.0000"

    details = client.get(f"/api/v1/loans/{loan_id}")
    assert details.status_code == 200
    repayments = details.json()["repayments"]
    assert len(repayments) == 24
    assert sum(Decimal(item["principal_amount"]) for item in repayments) == Decimal(
        "12000.0000"
    )

    repayment = repayments[0]
    api["current_actor"]["id"] = api["customer_user_id"]
    paid = client.post(
        f"/api/v1/loans/{loan_id}/repayments/{repayment['id']}/pay",
        params={"account_id": account["id"]},
        headers={"Idempotency-Key": "repayment-key-0001"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    replay = client.post(
        f"/api/v1/loans/{loan_id}/repayments/{repayment['id']}/pay",
        params={"account_id": account["id"]},
        headers={"Idempotency-Key": "repayment-key-0001"},
    )
    assert replay.status_code == 200
    assert replay.json()["id"] == paid.json()["id"]

    with Session(api["engine"]) as session:
        loan = session.get(Loan, UUID(loan_id))
        application_record = session.get(LoanApplication, UUID(application_id))
        assert loan is not None and application_record is not None
        assert loan.outstanding_balance < loan.principal
        assert application_record.status == "disbursed"
        assert session.scalar(
            select(Transaction.id).where(
                Transaction.transaction_type == "loan_disbursement"
            )
        )


def test_loan_rejection_and_account_closure_rules(
    banking_api: dict[str, object],
) -> None:
    api = banking_api
    client = api["client"]
    account = open_active_account(api)
    payload = {
        "customer_id": str(api["customer_id"]),
        "disbursement_account_id": account["id"],
        "loan_type": "education",
        "requested_amount": "5000.00",
        "requested_term_months": 36,
        "declared_monthly_income": "4000.00",
    }
    application = client.post("/api/v1/loans/applications", json=payload)
    assert application.status_code == 201
    rejected = client.post(
        f"/api/v1/loans/applications/{application.json()['id']}/reject",
        json={"reason": "Incomplete supporting information"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    account_id = account["id"]
    with Session(api["engine"]) as session:
        account_row = session.get(BankAccount, UUID(account_id))
        assert account_row is not None
        account_row.current_balance = Decimal("100.00")
        session.commit()
    assert client.delete(f"/api/v1/accounts/{account_id}").status_code == 409
    api["current_actor"]["id"] = api["customer_user_id"]
    assert client.delete(f"/api/v1/accounts/{account_id}").status_code == 409

    with Session(api["engine"]) as session:
        account_row = session.get(BankAccount, UUID(account_id))
        assert account_row is not None
        account_row.current_balance = Decimal("0")
        session.commit()
    api["current_actor"]["id"] = api["staff_user_id"]
    closed = client.delete(f"/api/v1/accounts/{account_id}")
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
