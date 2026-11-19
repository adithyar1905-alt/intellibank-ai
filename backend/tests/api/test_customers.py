from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import UUID

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
    BankAccount,
    Base,
    Customer,
    FraudAlert,
    KYCDocument,
    Role,
    Transaction,
    User,
)


@pytest.fixture
def customer_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    encryption_key = Fernet.generate_key().decode("ascii")
    storage_path = tmp_path / "private-documents"
    monkeypatch.setenv("KYC_ENCRYPTION_KEY", encryption_key)
    monkeypatch.setenv("KYC_STORAGE_PATH", str(storage_path))
    get_settings.cache_clear()

    database_path = tmp_path / "customers.db"
    engine = create_database_engine(f"sqlite+pysqlite:///{database_path}")
    Base.metadata.create_all(engine)

    staff_id = UUID("10000000-0000-4000-8000-000000000001")
    customer_user_id = UUID("10000000-0000-4000-8000-000000000002")
    with Session(engine) as session:
        staff_role = Role(name="Bank Employee")
        customer_role = Role(name="Customer")
        staff_user = User(
            id=staff_id,
            email="staff@example.test",
            password_hash="test-hash",
            roles=[staff_role],
        )
        customer_user = User(
            id=customer_user_id,
            email="customer@example.test",
            password_hash="test-hash",
            roles=[customer_role],
        )
        session.add_all([staff_user, customer_user])
        session.commit()

    actor_id = {"value": staff_id}

    def override_db():
        with Session(engine) as session:
            yield session

    def override_current_user():
        with Session(engine) as session:
            user = session.scalar(
                select(User)
                .options(selectinload(User.roles))
                .where(User.id == actor_id["value"])
            )
            assert user is not None
            return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_current_user
    with TestClient(app) as client:
        yield {
            "client": client,
            "engine": engine,
            "staff_id": staff_id,
            "customer_user_id": customer_user_id,
            "actor_id": actor_id,
            "storage_path": storage_path,
            "encryption_key": encryption_key,
        }
    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()


def create_customer(api: dict[str, object]) -> dict[str, object]:
    client = api["client"]
    response = client.post(
        "/api/v1/customers",
        json={
            "user_id": str(api["customer_user_id"]),
            "first_name": "Ada",
            "last_name": "Lovelace",
            "date_of_birth": "1815-12-10",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_customer_crud_search_status_and_audit(customer_api: dict[str, object]) -> None:
    api = customer_api
    client = api["client"]
    invalid = client.post(
        "/api/v1/customers",
        json={
            "user_id": str(api["customer_user_id"]),
            "first_name": " ",
            "last_name": "Lovelace",
        },
    )
    assert invalid.status_code == 422
    created = create_customer(api)
    customer_id = created["id"]
    duplicate = client.post(
        "/api/v1/customers",
        json={
            "user_id": str(api["customer_user_id"]),
            "first_name": "Ada",
            "last_name": "Lovelace",
        },
    )
    assert duplicate.status_code == 409

    updated = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={
            "first_name": "Augusta",
            "email": "ADA.NEW@example.com",
            "phone_number": "+15551234567",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["first_name"] == "Augusta"
    assert updated.json()["email"] == "ada.new@example.com"
    assert updated.json()["phone_number"] == "+15551234567"

    search = client.get("/api/v1/customers", params={"query": "Augusta"})
    assert search.status_code == 200
    assert [item["id"] for item in search.json()] == [customer_id]

    deactivated = client.delete(f"/api/v1/customers/{customer_id}")
    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == "inactive"
    with Session(api["engine"]) as session:
        customer = session.get(Customer, UUID(customer_id))
        customer_user = session.get(User, api["customer_user_id"])
        actions = set(
            session.scalars(
                select(AuditLog.action).where(AuditLog.resource_id == UUID(customer_id))
            )
        )
        assert customer is not None
        assert customer_user is not None and not customer_user.is_active
        assert actions == {
            "customer.create",
            "customer.update",
            "customer.status_change",
        }


def test_customer_self_access_and_role_restrictions(
    customer_api: dict[str, object],
) -> None:
    api = customer_api
    client = api["client"]
    created = create_customer(api)
    customer_id = created["id"]
    api["actor_id"]["value"] = api["customer_user_id"]

    own_profile = client.get(f"/api/v1/customers/{customer_id}")
    assert own_profile.status_code == 200
    assert own_profile.json()["id"] == customer_id
    assert client.get("/api/v1/customers").status_code == 403
    assert client.patch(
        f"/api/v1/customers/{customer_id}/status", json={"status": "blocked"}
    ).status_code == 403


def test_kyc_document_is_encrypted_and_reviewed(customer_api: dict[str, object]) -> None:
    api = customer_api
    client = api["client"]
    created = create_customer(api)
    customer_id = created["id"]
    file_content = b"%PDF-1.7\nprivate KYC document"

    unsupported = client.post(
        f"/api/v1/customers/{customer_id}/kyc-documents",
        data={"document_type": "passport"},
        files={"file": ("unsupported.txt", b"not a supported document", "text/plain")},
    )
    assert unsupported.status_code == 415

    upload = client.post(
        f"/api/v1/customers/{customer_id}/kyc-documents",
        data={"document_type": "passport", "document_number": "AB123456"},
        files={"file": ("passport.pdf", file_content, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    document = upload.json()
    assert document["document_number_last4"] == "3456"
    assert document["status"] == "pending"

    with Session(api["engine"]) as session:
        document_record = session.scalar(
            select(KYCDocument).where(KYCDocument.id == UUID(document["id"]))
        )
        assert document_record is not None
        stored_file = api["storage_path"] / document_record.document_reference
        encrypted = stored_file.read_bytes()
        assert file_content not in encrypted
        assert Fernet(api["encryption_key"].encode("ascii")).decrypt(encrypted) == file_content

    reviewed = client.patch(
        f"/api/v1/customers/{customer_id}/kyc-documents/{document['id']}",
        json={"status": "verified"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "verified"

    downloaded = client.get(
        f"/api/v1/customers/{customer_id}/kyc-documents/{document['id']}/download"
    )
    assert downloaded.status_code == 200
    assert downloaded.content == file_content
    assert downloaded.headers["cache-control"] == "no-store"
    profile = client.get(f"/api/v1/customers/{customer_id}")
    assert profile.json()["kyc_status"] == "verified"


def test_account_history_and_risk_profile(customer_api: dict[str, object]) -> None:
    api = customer_api
    client = api["client"]
    created = create_customer(api)
    customer_id = UUID(created["id"])

    with Session(api["engine"]) as session:
        customer = session.get(Customer, customer_id)
        assert customer is not None
        account_type = AccountType(code="checking", name="Checking")
        account = BankAccount(
            customer=customer,
            account_type=account_type,
            account_number="0000123456789",
        )
        transaction = Transaction(
            reference="TXN-CUSTOMER-1",
            account=account,
            transaction_type="deposit",
            amount=Decimal("25.50"),
            currency="USD",
            status="completed",
        )
        external_account = BankAccount(
            customer=Customer(
                user_id=api["staff_id"],
                customer_number="CUST-EXTERNAL",
                first_name="Bank",
                last_name="Customer",
            ),
            account_type=account_type,
            account_number="0000098765432",
        )
        incoming_transaction = Transaction(
            reference="TXN-CUSTOMER-2",
            account=external_account,
            related_account=account,
            transaction_type="transfer",
            amount=Decimal("10.00"),
            currency="USD",
            status="completed",
        )
        alert = FraudAlert(
            customer=customer,
            score=Decimal("0.85"),
            severity="high",
            status="open",
            description="Unusual transaction pattern",
        )
        session.add_all([transaction, incoming_transaction, alert])
        session.commit()

    history = client.get(f"/api/v1/customers/{customer_id}/account-history")
    assert history.status_code == 200
    assert len(history.json()) == 2
    assert {item["reference"] for item in history.json()} == {
        "TXN-CUSTOMER-1",
        "TXN-CUSTOMER-2",
    }
    assert all(item["account_number_last4"] == "6789" for item in history.json())

    risk = client.get(f"/api/v1/customers/{customer_id}/risk-profile")
    assert risk.status_code == 200
    assert risk.json()["risk_level"] == "high"
    assert risk.json()["risk_score"] == pytest.approx(0.85)
    assert risk.json()["open_alert_count"] == 1
