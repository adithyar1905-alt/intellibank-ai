import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import DEFAULT_ROLE_NAMES
from app.database import create_database_engine
from app.models import Base, Role, User
from app.services.authentication.demo_accounts import import_demo_accounts


class DemoAccountImportTests(unittest.TestCase):
    def setUp(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.directory = Path(temp_dir.name)
        self.database_path = self.directory / "test.db"
        self.engine = create_database_engine(
            "sqlite+pysqlite:///" + self.database_path.as_posix()
        )
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            session.add_all(Role(name=name) for name in DEFAULT_ROLE_NAMES)
            session.commit()

    def create_workbook(self, rows: list[tuple[str, str, str]]) -> Path:
        path = self.directory / "demo-accounts.xlsx"
        workbook = Workbook()
        accounts = workbook.active
        accounts.title = "Demo Login Accounts"
        accounts.append(["Role", "Email", "Demo Password"])
        for row in rows:
            accounts.append(row)
        extra = workbook.create_sheet("Authenticator & Permissions")
        extra.append(["Role", "Authenticator", "Access"])
        extra.append(["Super Admin", "must-not-be-imported", "All modules"])
        workbook.save(path)
        workbook.close()
        return path

    def test_import_hashes_password_and_maps_workbook_role(self) -> None:
        workbook = self.create_workbook(
            [("Bank Manager", "manager@example.com", "demo-password")]
        )

        with Session(self.engine) as session:
            result = import_demo_accounts(workbook, session)

        self.assertEqual(result.imported, 1)
        self.assertEqual(result.skipped_existing, 0)
        with Session(self.engine) as session:
            user = session.scalar(
                select(User).where(User.email == "manager@example.com")
            )
            self.assertIsNotNone(user)
            self.assertNotEqual(user.password_hash, "demo-password")
            self.assertTrue(user.password_hash.startswith("$argon2"))
            self.assertEqual([role.name for role in user.roles], ["Branch Manager"])
            self.assertFalse(user.is_verified)

    def test_import_is_idempotent_and_does_not_replace_existing_password(self) -> None:
        workbook = self.create_workbook(
            [("Customer", "customer@example.com", "workbook-password")]
        )
        with Session(self.engine) as session:
            result = import_demo_accounts(workbook, session)
            first_hash = session.scalar(
                select(User.password_hash).where(
                    User.email == "customer@example.com"
                )
            )
        self.assertEqual(result.imported, 1)

        with Session(self.engine) as session:
            result = import_demo_accounts(workbook, session)
            current_hash = session.scalar(
                select(User.password_hash).where(
                    User.email == "customer@example.com"
                )
            )

        self.assertEqual(result.imported, 0)
        self.assertEqual(result.skipped_existing, 1)
        self.assertEqual(current_hash, first_hash)

    def test_invalid_workbook_row_fails_without_importing_any_accounts(self) -> None:
        workbook = self.create_workbook(
            [
                ("Customer", "valid@example.com", "valid-password"),
                ("Unknown Role", "invalid@example.com", "other-password"),
            ]
        )

        with Session(self.engine) as session:
            with self.assertRaisesRegex(ValueError, "Unsupported role"):
                import_demo_accounts(workbook, session)

        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(User.id)), None)

    def test_duplicate_email_is_rejected(self) -> None:
        workbook = self.create_workbook(
            [
                ("Customer", "same@example.com", "first-password"),
                ("Customer", "SAME@example.com", "second-password"),
            ]
        )

        with Session(self.engine) as session:
            with self.assertRaisesRegex(ValueError, "Duplicate email"):
                import_demo_accounts(workbook, session)

        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(User.id)), None)


if __name__ == "__main__":
    unittest.main()
