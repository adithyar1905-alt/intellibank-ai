from __future__ import annotations

import argparse
from pathlib import Path

from app.database import get_session_factory
from app.services.authentication.demo_accounts import import_demo_accounts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import demo login accounts into the configured IntelliBank database."
    )
    parser.add_argument(
        "workbook",
        type=Path,
        help="Path to IntelliFlow_Bank_AI_Demo_Accounts_and_Permissions.xlsx",
    )
    args = parser.parse_args()

    with get_session_factory()() as session:
        result = import_demo_accounts(args.workbook, session)

    print(
        f"Demo account import complete: {result.imported} added, "
        f"{result.skipped_existing} existing accounts left unchanged."
    )
    print(
        "Passwords were stored as Argon2 hashes. Workbook authenticator codes "
        "were not imported; configure MFA through the authenticated setup flow."
    )


if __name__ == "__main__":
    main()
