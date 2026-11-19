from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai_services.chatbot.adapter import (
    ConfiguredProviderAdapter,
    NoProviderAdapter,
    get_assistant_adapter,
)
import app.ai_services.chatbot.adapter as adapter_module
from app.ai_services.chatbot.service import BankingAssistantService
from app.api.v1 import banking_assistant
from app.core.authentication import get_current_user
from app.database import create_database_engine, get_db
from app.main import app
from app.models import Base, Customer, Role, User


@pytest.fixture
def assistant_api(tmp_path: Path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'assistant.db'}")
    Base.metadata.create_all(engine)
    user_id = uuid4()
    outsider_id = uuid4()
    actor = {"id": user_id}
    with Session(engine) as session:
        role = Role(name="Customer")
        user = User(
            id=user_id,
            email="assistant-customer@example.com",
            password_hash="test-hash",
            is_verified=True,
            roles=[role],
        )
        outsider = User(
            id=outsider_id,
            email="outsider@example.com",
            password_hash="test-hash",
            is_verified=True,
            roles=[role],
        )
        session.add_all(
            [
                outsider,
                Customer(
                    user=user,
                    customer_number="CUST-AI-0001",
                    first_name="Verified",
                    last_name="Customer",
                    status="active",
                ),
            ]
        )
        session.commit()

    def override_db():
        with Session(engine) as session:
            yield session

    def override_user():
        with Session(engine) as session:
            return session.scalar(
                select(User)
                .options(selectinload(User.roles))
                .where(User.id == actor["id"])
            )

    app.include_router(banking_assistant.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    old_service = banking_assistant._service
    banking_assistant._service = BankingAssistantService(max_requests=2)
    try:
        with TestClient(app) as client:
            yield client, actor, engine, outsider_id
    finally:
        banking_assistant._service = old_service
        app.dependency_overrides.clear()
        engine.dispose()


def test_adapter_safe_default_and_configured_behavior():
    assert "not configured" in NoProviderAdapter().answer("hello")
    assert "not enabled" in ConfiguredProviderAdapter("example").answer("hello")


def test_openai_compatible_adapter_sends_only_generic_question(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "Use a budget."}}]}
            ).encode()

    captured = {}

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        captured["authorization"] = request.headers["Authorization"]
        return FakeResponse()

    monkeypatch.setattr(
        adapter_module,
        "get_settings",
        lambda: SimpleNamespace(
            ai_assistant_provider="openai_compatible",
            ai_assistant_api_url="https://example.test/v1/chat/completions",
            ai_assistant_api_key="secret",
            ai_assistant_model="safe-model",
            ai_assistant_timeout_seconds=3,
        ),
    )
    monkeypatch.setattr(adapter_module, "urlopen", fake_urlopen)

    adapter = get_assistant_adapter()
    assert adapter.answer("How do I build an emergency fund?") == "Use a budget."
    assert captured["body"]["messages"][0]["role"] == "system"
    assert captured["body"]["messages"][1]["content"] == (
        "How do I build an emergency fund?"
    )
    assert "tools" not in captured["body"]
    assert captured["timeout"] == 3
    assert captured["authorization"] == "Bearer secret"


def test_openai_compatible_missing_config_is_safe(monkeypatch):
    monkeypatch.setattr(
        adapter_module,
        "get_settings",
        lambda: SimpleNamespace(
            ai_assistant_provider="openai_compatible",
            ai_assistant_api_url=None,
            ai_assistant_api_key=None,
            ai_assistant_model=None,
            ai_assistant_timeout_seconds=10,
        ),
    )
    adapter = get_assistant_adapter()
    assert "configured incompletely" in adapter.answer("What is APR?")


def test_assistant_refuses_transaction_execution_and_limits_requests(assistant_api):
    client, _, _, _ = assistant_api
    first = client.post(
        "/api/v1/banking-assistant/chat", json={"message": "Please transfer $10"}
    )
    assert first.status_code == 200
    assert first.json()["intent"] == "mutation_refused"
    assert "cannot execute" in first.json()["answer"]

    assert client.post(
        "/api/v1/banking-assistant/chat", json={"message": "balance"}
    ).status_code == 200
    assert client.post(
        "/api/v1/banking-assistant/chat", json={"message": "loan"}
    ).status_code == 429


def test_assistant_requires_verified_customer(assistant_api):
    client, actor, _, outsider_id = assistant_api
    actor["id"] = outsider_id
    response = client.post(
        "/api/v1/banking-assistant/chat", json={"message": "show my balance"}
    )
    assert response.status_code == 403


def test_assistant_history_persists_across_requests(assistant_api):
    client, _, _, _ = assistant_api
    response = client.post(
        "/api/v1/banking-assistant/chat",
        json={"message": "What is a healthy emergency fund?"},
    )
    assert response.status_code == 200

    history = client.get("/api/v1/banking-assistant/history")
    assert history.status_code == 200
    entries = history.json()
    assert entries[0] == {
        "role": "user",
        "content": "What is a healthy emergency fund?",
    }
    assert entries[1]["role"] == "assistant"
