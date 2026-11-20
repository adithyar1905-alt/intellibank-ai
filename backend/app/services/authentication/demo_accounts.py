from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from email_validator import EmailNotValidError, validate_email
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import Role, User


ACCOUNT_SHEET = "Demo Login Accounts"
ROLE_MAP = {
    "Super Admin": "Super Admin",
    "Bank Manager": "Branch Manager",
    "Bank Employee": "Bank Employee",
    "Customer": "Customer",
}
REQUIRED_HEADERS = ("Role", "Email", "Demo Password")


@dataclass(frozen=True)
class DemoAccountImportResult:
    imported: int
    skipped_existing: int


def import_demo_accounts(
    workbook_path: Path, session: Session
) -> DemoAccountImportResult:
    """Provision demo logins from the workbook without persisting plaintext credentials."""
    try:
        workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    except (OSError, InvalidFileException) as exc:
        raise ValueError("Unable to read the demo accounts workbook.") from exc

    try:
        if ACCOUNT_SHEET not in workbook.sheetnames:
            raise ValueError(f"Workbook is missing the {ACCOUNT_SHEET!r} worksheet.")

        worksheet = workbook[ACCOUNT_SHEET]
        header_values = next(
            worksheet.iter_rows(min_row=1, max_row=1, values_only=True), ()
        )
        headers = tuple(str(value).strip() if value is not None else "" for value in header_values)
        if any(header not in headers for header in REQUIRED_HEADERS):
            raise ValueError(
                f"The {ACCOUNT_SHEET!r} worksheet must include Role, Email, and Demo Password columns."
            )
        indexes = {header: headers.index(header) for header in REQUIRED_HEADERS}

        accounts: list[tuple[int, str, str, str]] = []
        seen_emails: set[str] = set()
        for row_number, row in enumerate(
            worksheet.iter_rows(min_row=2, values_only=True), start=2
        ):
            if not any(value is not None for value in row):
                continue

            role_value = row[indexes["Role"]] if indexes["Role"] < len(row) else None
            email_value = row[indexes["Email"]] if indexes["Email"] < len(row) else None
            password_value = (
                row[indexes["Demo Password"]]
                if indexes["Demo Password"] < len(row)
                else None
            )
            role = str(role_value).strip() if role_value is not None else ""
            email = str(email_value).strip() if email_value is not None else ""
            password = str(password_value) if password_value is not None else ""

            if role not in ROLE_MAP:
                raise ValueError(f"Unsupported role on workbook row {row_number}.")
            try:
                email = validate_email(
                    email, check_deliverability=False
                ).normalized.lower()
            except EmailNotValidError as exc:
                raise ValueError(
                    f"Invalid email address on workbook row {row_number}."
                ) from exc
            if not password or len(password) > 128:
                raise ValueError(f"Invalid demo password on workbook row {row_number}.")
            if email in seen_emails:
                raise ValueError(f"Duplicate email address on workbook row {row_number}.")

            seen_emails.add(email)
            accounts.append((row_number, ROLE_MAP[role], email, password))

        if not accounts:
            raise ValueError("The demo accounts worksheet contains no login accounts.")

        required_roles = {role_name for _, role_name, _, _ in accounts}
        roles = {
            role.name: role
            for role in session.scalars(
                select(Role).where(Role.name.in_(required_roles))
            ).all()
        }
        missing_roles = required_roles - roles.keys()
        if missing_roles:
            missing = ", ".join(sorted(missing_roles))
            raise ValueError(
                f"Database roles are not provisioned: {missing}. Apply database migrations first."
            )

        imported = 0
        skipped_existing = 0
        for _, role_name, email, password in accounts:
            existing = session.scalar(select(User.id).where(User.email == email))
            if existing is not None:
                skipped_existing += 1
                continue

            session.add(
                User(
                    email=email,
                    password_hash=hash_password(password),
                    is_active=True,
                    is_verified=False,
                    roles=[roles[role_name]],
                )
            )
            imported += 1

        session.commit()
        return DemoAccountImportResult(
            imported=imported, skipped_existing=skipped_existing
        )
    except Exception:
        session.rollback()
        raise
    finally:
        workbook.close()
