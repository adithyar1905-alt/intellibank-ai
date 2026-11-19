"""account, transaction, ledger, and loan workflows

Revision ID: f41a8b7c2d90
Revises: e3c58bf448c2
"""
from typing import Sequence, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision: str = "f41a8b7c2d90"
down_revision: Union[str, None] = "e3c58bf448c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ACCOUNT_TYPES = (
    (UUID("20000000-0000-4000-8000-000000000001"), "savings", "Savings Account"),
    (UUID("20000000-0000-4000-8000-000000000002"), "current", "Current Account"),
    (UUID("20000000-0000-4000-8000-000000000003"), "fixed_deposit", "Fixed Deposit"),
    (UUID("20000000-0000-4000-8000-000000000004"), "recurring_deposit", "Recurring Deposit"),
)


def upgrade() -> None:
    op.add_column(
        "bank_accounts",
        sa.Column("daily_limit", sa.Numeric(19, 4), nullable=False, server_default="10000"),
    )
    op.add_column(
        "bank_accounts",
        sa.Column("monthly_limit", sa.Numeric(19, 4), nullable=False, server_default="100000"),
    )
    op.add_column("bank_accounts", sa.Column("approved_by", sa.Uuid(), nullable=True))
    op.add_column(
        "bank_accounts", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "bank_accounts", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_bank_accounts_approved_by_users",
        "bank_accounts",
        "users",
        ["approved_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint("ck_bank_accounts_valid_status", "bank_accounts", type_="check")
    op.create_check_constraint(
        "valid_status",
        "bank_accounts",
        "status IN ('pending_approval', 'pending_activation', 'active', 'frozen', 'closed')",
    )
    op.create_check_constraint(
        "positive_daily_limit", "bank_accounts", "daily_limit > 0"
    )
    op.create_check_constraint(
        "positive_monthly_limit", "bank_accounts", "monthly_limit > 0"
    )

    op.add_column("transactions", sa.Column("initiated_by", sa.Uuid(), nullable=True))
    op.add_column(
        "transactions", sa.Column("idempotency_key", sa.String(128), nullable=True)
    )
    op.add_column("transactions", sa.Column("request_hash", sa.String(64), nullable=True))
    op.add_column(
        "transactions",
        sa.Column("counterparty_reference", sa.String(64), nullable=True),
    )
    op.add_column(
        "transactions", sa.Column("reversed_transaction_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_transactions_initiated_by_users",
        "transactions",
        "users",
        ["initiated_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_transactions_reversed_transaction_id_transactions",
        "transactions",
        "transactions",
        ["reversed_transaction_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_transactions_idempotency_key", "transactions", ["idempotency_key"]
    )
    op.create_unique_constraint(
        "uq_transactions_reversed_transaction_id",
        "transactions",
        ["reversed_transaction_id"],
    )
    op.create_index(
        "ix_transactions_initiated_by", "transactions", ["initiated_by"]
    )
    op.create_index(
        "ix_transactions_account_type_created",
        "transactions",
        ["account_id", "transaction_type", "created_at"],
    )
    op.drop_constraint(
        "ck_transactions_valid_transaction_type", "transactions", type_="check"
    )
    op.create_check_constraint(
        "valid_transaction_type",
        "transactions",
        "transaction_type IN ('deposit', 'withdrawal', 'transfer', 'payment', 'fee', "
        "'loan_disbursement', 'loan_repayment', 'adjustment', 'neft', 'rtgs', 'imps', "
        "'upi', 'reversal')",
    )
    op.drop_constraint("ck_transactions_valid_status", "transactions", type_="check")
    op.create_check_constraint(
        "valid_status",
        "transactions",
        "status IN ('pending', 'completed', 'failed', 'reversed', 'rejected')",
    )

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("entry_type", sa.String(10), nullable=False),
        sa.Column("amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("balance_after", sa.Numeric(19, 4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("amount > 0", name="ck_ledger_entries_positive_amount"),
        sa.CheckConstraint(
            "entry_type IN ('debit', 'credit')",
            name="ck_ledger_entries_valid_entry_type",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            ondelete="RESTRICT",
            name="fk_ledger_entries_transaction_id_transactions",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["bank_accounts.id"],
            ondelete="RESTRICT",
            name="fk_ledger_entries_account_id_bank_accounts",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ledger_entries"),
    )
    op.create_index(
        "ix_ledger_entries_transaction_id", "ledger_entries", ["transaction_id"]
    )
    op.create_index("ix_ledger_entries_account_id", "ledger_entries", ["account_id"])
    op.create_index(
        "ix_ledger_entries_account_created",
        "ledger_entries",
        ["account_id", "created_at"],
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION prevent_ledger_entry_mutation() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'ledger entries are immutable';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            """
            CREATE TRIGGER ledger_entries_immutable
            BEFORE UPDATE OR DELETE ON ledger_entries
            FOR EACH ROW EXECUTE FUNCTION prevent_ledger_entry_mutation()
            """
        )

    op.add_column(
        "loans",
        sa.Column("loan_type", sa.String(30), nullable=False, server_default="personal"),
    )
    op.add_column(
        "loans",
        sa.Column(
            "outstanding_balance",
            sa.Numeric(19, 4),
            nullable=False,
            server_default="0",
        ),
    )
    op.drop_constraint("ck_loans_valid_status", "loans", type_="check")
    op.create_check_constraint(
        "valid_status",
        "loans",
        "status IN ('active', 'paid_off', 'defaulted', 'closed', 'pending_disbursement')",
    )

    op.add_column(
        "loan_applications",
        sa.Column("loan_type", sa.String(30), nullable=False, server_default="personal"),
    )
    op.add_column(
        "loan_applications", sa.Column("rejection_reason", sa.String(500), nullable=True)
    )
    op.add_column(
        "loan_applications", sa.Column("reviewed_by", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "loan_applications",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "loan_applications",
        sa.Column("disbursement_account_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "loan_applications",
        sa.Column(
            "declared_monthly_income",
            sa.Numeric(19, 4),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_foreign_key(
        "fk_loan_applications_reviewed_by_users",
        "loan_applications",
        "users",
        ["reviewed_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_loan_applications_disbursement_account_id_bank_accounts",
        "loan_applications",
        "bank_accounts",
        ["disbursement_account_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        "ck_loan_applications_valid_status", "loan_applications", type_="check"
    )
    op.create_check_constraint(
        "valid_status",
        "loan_applications",
        "status IN ('submitted', 'under_review', 'approved', 'rejected', 'withdrawn', 'disbursed')",
    )

    op.add_column(
        "loan_repayments",
        sa.Column(
            "principal_amount",
            sa.Numeric(19, 4),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "loan_repayments",
        sa.Column(
            "interest_amount",
            sa.Numeric(19, 4),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        "nonnegative_principal_amount",
        "loan_repayments",
        "principal_amount >= 0",
    )
    op.create_check_constraint(
        "nonnegative_interest_amount",
        "loan_repayments",
        "interest_amount >= 0",
    )

    op.create_table(
        "loan_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("document_reference", sa.String(512), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["loan_applications.id"],
            ondelete="CASCADE",
            name="fk_loan_documents_application_id_loan_applications",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_loan_documents"),
    )
    op.create_index(
        "ix_loan_documents_application_id", "loan_documents", ["application_id"]
    )

    account_types = sa.table(
        "account_types",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String(30)),
        sa.column("name", sa.String(80)),
        sa.column("minimum_balance", sa.Numeric(19, 4)),
        sa.column("allows_overdraft", sa.Boolean()),
    )
    op.bulk_insert(
        account_types,
        [
            {
                "id": account_id,
                "code": code,
                "name": name,
                "minimum_balance": 0,
                "allows_overdraft": False,
            }
            for account_id, code, name in ACCOUNT_TYPES
        ],
    )


def downgrade() -> None:
    account_types = sa.table("account_types", sa.column("code", sa.String(30)))
    op.execute(
        account_types.delete().where(
            account_types.c.code.in_([code for _, code, _ in ACCOUNT_TYPES])
        )
    )
    op.drop_index("ix_loan_documents_application_id", table_name="loan_documents")
    op.drop_table("loan_documents")
    op.drop_constraint(
        "ck_loan_repayments_nonnegative_interest_amount",
        "loan_repayments",
        type_="check",
    )
    op.drop_constraint(
        "ck_loan_repayments_nonnegative_principal_amount",
        "loan_repayments",
        type_="check",
    )
    op.drop_column("loan_repayments", "interest_amount")
    op.drop_column("loan_repayments", "principal_amount")
    op.drop_constraint(
        "ck_loan_applications_valid_status", "loan_applications", type_="check"
    )
    op.create_check_constraint(
        "valid_status",
        "loan_applications",
        "status IN ('submitted', 'under_review', 'approved', 'rejected', 'withdrawn')",
    )
    op.drop_constraint(
        "fk_loan_applications_disbursement_account_id_bank_accounts",
        "loan_applications",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_loan_applications_reviewed_by_users",
        "loan_applications",
        type_="foreignkey",
    )
    for column in (
        "disbursement_account_id",
        "declared_monthly_income",
        "reviewed_at",
        "reviewed_by",
        "rejection_reason",
        "loan_type",
    ):
        op.drop_column("loan_applications", column)
    op.drop_constraint("ck_loans_valid_status", "loans", type_="check")
    op.create_check_constraint(
        "valid_status",
        "loans",
        "status IN ('active', 'paid_off', 'defaulted', 'closed')",
    )
    op.drop_column("loans", "outstanding_balance")
    op.drop_column("loans", "loan_type")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER ledger_entries_immutable ON ledger_entries")
        op.execute("DROP FUNCTION prevent_ledger_entry_mutation()")
    op.drop_index("ix_ledger_entries_account_created", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_account_id", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_transaction_id", table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_constraint("ck_transactions_valid_status", "transactions", type_="check")
    op.create_check_constraint(
        "valid_status",
        "transactions",
        "status IN ('pending', 'completed', 'failed', 'reversed')",
    )
    op.drop_constraint(
        "ck_transactions_valid_transaction_type", "transactions", type_="check"
    )
    op.create_check_constraint(
        "valid_transaction_type",
        "transactions",
        "transaction_type IN ('deposit', 'withdrawal', 'transfer', 'payment', "
        "'fee', 'loan_disbursement', 'loan_repayment', 'adjustment')",
    )
    op.drop_index("ix_transactions_account_type_created", table_name="transactions")
    op.drop_index("ix_transactions_initiated_by", table_name="transactions")
    op.drop_constraint(
        "uq_transactions_reversed_transaction_id", "transactions", type_="unique"
    )
    op.drop_constraint(
        "uq_transactions_idempotency_key", "transactions", type_="unique"
    )
    op.drop_constraint(
        "fk_transactions_reversed_transaction_id_transactions",
        "transactions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_transactions_initiated_by_users", "transactions", type_="foreignkey"
    )
    for column in (
        "reversed_transaction_id",
        "counterparty_reference",
        "request_hash",
        "idempotency_key",
        "initiated_by",
    ):
        op.drop_column("transactions", column)
    op.drop_constraint(
        "ck_bank_accounts_positive_monthly_limit", "bank_accounts", type_="check"
    )
    op.drop_constraint(
        "ck_bank_accounts_positive_daily_limit", "bank_accounts", type_="check"
    )
    op.drop_constraint("ck_bank_accounts_valid_status", "bank_accounts", type_="check")
    op.create_check_constraint(
        "valid_status", "bank_accounts", "status IN ('active', 'frozen', 'closed')"
    )
    op.drop_constraint(
        "fk_bank_accounts_approved_by_users", "bank_accounts", type_="foreignkey"
    )
    for column in ("closed_at", "approved_at", "approved_by", "monthly_limit", "daily_limit"):
        op.drop_column("bank_accounts", column)
