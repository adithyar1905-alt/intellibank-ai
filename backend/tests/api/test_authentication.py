import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pyotp
from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.auth import get_password_reset_sender
from app.config import get_settings
from app.core.authorization import require_permissions, require_roles
from app.core.permissions import DEFAULT_ROLE_NAMES
from app.core.security import verify_password
from app.database import create_database_engine, get_db
from app.main import app
from app.models import Base, Permission, Role, User
from app.models.auth import AuthToken, UserMFA


class AuthenticationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.settings_environment = patch.dict(
            os.environ,
            {
                "JWT_SECRET_KEY": "test-secret-key-with-at-least-32-bytes",
                "MFA_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
                "ACCESS_TOKEN_MINUTES": "15",
                "REFRESH_TOKEN_DAYS": "30",
                "SMTP_HOST": "smtp.example.test",
                "SMTP_FROM_EMAIL": "no-reply@example.com",
            },
        )
        cls.settings_environment.start()
        get_settings.cache_clear()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.settings_environment.stop()
        get_settings.cache_clear()

    def setUp(self) -> None:
        temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_file.close()
        self.database_path = Path(temp_file.name)
        database_url = "sqlite+pysqlite:///" + self.database_path.as_posix()
        self.engine = create_database_engine(database_url)
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            session.add_all(
                Role(name=role_name)
                for role_name in DEFAULT_ROLE_NAMES
            )
            session.commit()

        def override_get_db():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.reset_tokens: list[str] = []
        self.reset_email_recipients: list[str] = []

        def capture_reset_email(email: str, token: str) -> None:
            self.reset_email_recipients.append(email)
            self.reset_tokens.append(token)

        app.dependency_overrides[get_password_reset_sender] = lambda: capture_reset_email

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.client.close()
        self.engine.dispose()
        self.database_path.unlink(missing_ok=True)

    def register(self, email: str = "customer@example.com") -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "a-very-long-test-password"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_registration_login_and_swagger_oauth_flow(self) -> None:
        tokens = self.register()
        registration_response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "second@example.com",
                "password": "another-long-password",
            },
        )
        self.assertEqual(registration_response.headers["cache-control"], "no-store")
        me = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["roles"], ["Customer"])

        with Session(self.engine) as session:
            user = session.scalar(select(User).where(User.email == "customer@example.com"))
            self.assertIsNotNone(user)
            self.assertNotEqual(user.password_hash, "a-very-long-test-password")
            self.assertTrue(user.password_hash.startswith("$argon2"))

        login = self.client.post(
            "/api/v1/auth/login",
            data={
                "username": "customer@example.com",
                "password": "a-very-long-test-password",
            },
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.assertIn("refresh_token", login.json())

        schema = self.client.get("/openapi.json").json()
        security = schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]
        self.assertEqual(security["flows"]["password"]["tokenUrl"], "/api/v1/auth/login")
        self.assertIn("application/x-www-form-urlencoded", schema["paths"]["/api/v1/auth/login"]["post"]["requestBody"]["content"])

    def test_refresh_rotates_tokens_and_logout_revokes_both(self) -> None:
        first = self.register()
        rotated = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": first["refresh_token"]},
        )
        self.assertEqual(rotated.status_code, 200, rotated.text)
        self.assertNotEqual(rotated.json()["refresh_token"], first["refresh_token"])

        old_refresh = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": first["refresh_token"]},
        )
        self.assertEqual(old_refresh.status_code, 401)

        logout = self.client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {rotated.json()['access_token']}"},
        )
        self.assertEqual(logout.status_code, 200, logout.text)
        rejected_access = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {rotated.json()['access_token']}"},
        )
        rejected_refresh = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": rotated.json()["refresh_token"]},
        )
        self.assertEqual(rejected_access.status_code, 401)
        self.assertEqual(rejected_refresh.status_code, 401)

    def test_password_reset_is_one_time_and_revokes_existing_sessions(self) -> None:
        tokens = self.register()
        unknown_request = self.client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "not-registered@example.com"},
        )
        self.assertEqual(unknown_request.status_code, 200)
        self.assertEqual(self.reset_tokens, [])
        request = self.client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "customer@example.com"},
        )
        self.assertEqual(request.status_code, 200, request.text)
        self.assertEqual(len(self.reset_tokens), 1)
        self.assertEqual(self.reset_email_recipients, ["customer@example.com"])
        with Session(self.engine) as session:
            reset_record = session.scalar(
                select(AuthToken).where(AuthToken.token_type == "password_reset")
            )
            self.assertNotEqual(
                reset_record.token_hash, self.reset_tokens[0]
            )

        reset = self.client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": self.reset_tokens[0],
                "new_password": "another-long-password",
            },
        )
        self.assertEqual(reset.status_code, 200, reset.text)
        replay = self.client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": self.reset_tokens[0],
                "new_password": "another-long-password",
            },
        )
        self.assertEqual(replay.status_code, 400)
        rejected_access = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        self.assertEqual(rejected_access.status_code, 401)

        login = self.client.post(
            "/api/v1/auth/login",
            data={
                "username": "customer@example.com",
                "password": "another-long-password",
            },
        )
        self.assertEqual(login.status_code, 200, login.text)

    def test_mfa_setup_confirmation_and_login_challenge(self) -> None:
        tokens = self.register()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        setup = self.client.post("/api/v1/auth/mfa/setup", headers=headers)
        self.assertEqual(setup.status_code, 200, setup.text)
        totp = pyotp.TOTP(setup.json()["secret"])

        confirmation = self.client.post(
            "/api/v1/auth/mfa/confirm",
            headers=headers,
            json={"code": totp.now()},
        )
        self.assertEqual(confirmation.status_code, 200, confirmation.text)
        self.assertTrue(confirmation.json()["enabled"])
        with Session(self.engine) as session:
            user = session.scalar(select(User).where(User.email == "customer@example.com"))
            self.assertTrue(verify_password("a-very-long-test-password", user.password_hash))
            mfa_settings = session.get(UserMFA, user.id)
            self.assertNotEqual(mfa_settings.encrypted_secret, setup.json()["secret"])

        missing_code = self.client.post(
            "/api/v1/auth/login",
            data={
                "username": "customer@example.com",
                "password": "a-very-long-test-password",
            },
        )
        self.assertEqual(missing_code.status_code, 401)

        current_counter = totp.timecode(datetime.now().astimezone())
        next_code = totp.at((current_counter + 1) * totp.interval)
        login = self.client.post(
            "/api/v1/auth/login",
            data={
                "username": "customer@example.com",
                "password": "a-very-long-test-password",
                "mfa_code": next_code,
            },
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(login.headers["cache-control"], "no-store")
        replayed_code = self.client.post(
            "/api/v1/auth/login",
            data={
                "username": "customer@example.com",
                "password": "a-very-long-test-password",
                "mfa_code": next_code,
            },
        )
        self.assertEqual(replayed_code.status_code, 401)

    def test_role_and_permission_dependencies_reject_unauthorized_user(self) -> None:
        tokens = self.register()
        with Session(self.engine) as session:
            user = session.scalar(select(User).where(User.email == "customer@example.com"))
            with self.assertRaises(HTTPException) as role_error:
                require_roles("Bank Admin")(user)
            self.assertEqual(role_error.exception.status_code, 403)

            with self.assertRaises(HTTPException) as permission_error:
                require_permissions("accounts:write")(user)
            self.assertEqual(permission_error.exception.status_code, 403)

            permission = Permission(
                name="accounts:write",
                resource="accounts",
                action="write",
            )
            user.roles[0].permissions.append(permission)
            bank_admin = session.scalar(select(Role).where(Role.name == "Bank Admin"))
            user.roles.append(bank_admin)
            session.commit()
            self.assertIs(require_permissions("accounts:write")(user), user)

        response = self.client.get(
            "/api/v1/auth/roles",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("Super Admin", response.json())

    def test_customer_cannot_list_administrative_roles(self) -> None:
        tokens = self.register()
        response = self.client.get(
            "/api/v1/auth/roles",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        self.assertEqual(response.status_code, 403)
