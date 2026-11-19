"""AI fraud and AML monitoring workflows

Revision ID: c82d13a7f490
Revises: f41a8b7c2d90
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c82d13a7f490"
down_revision: Union[str, None] = "f41a8b7c2d90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("valid_status", "transactions", type_="check")
    op.create_check_constraint(
        "valid_status",
        "transactions",
        "status IN ('pending', 'completed', 'failed', 'reversed', 'rejected', "
        "'review_required')",
    )
    op.create_table(
        "aml_rules",
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("code", name="pk_aml_rules"),
    )
    op.create_table(
        "aml_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_number", sa.String(length=40), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("rule_code", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("assigned_to", sa.Uuid(), nullable=True),
        sa.Column("resolution", sa.String(length=2000), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('open', 'investigating', 'escalated', 'closed')",
            name="valid_status",
        ),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="valid_severity",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to"],
            ["users.id"],
            name="fk_aml_cases_assigned_to_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_aml_cases_customer_id_customers",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name="fk_aml_cases_transaction_id_transactions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_aml_cases"),
        sa.UniqueConstraint("case_number", name="uq_aml_cases_case_number"),
        sa.UniqueConstraint(
            "transaction_id", "rule_code", name="uq_aml_cases_transaction_id"
        ),
    )
    op.create_index("ix_aml_cases_customer_id", "aml_cases", ["customer_id"])
    op.create_index("ix_aml_cases_transaction_id", "aml_cases", ["transaction_id"])
    op.create_index(
        "ix_aml_cases_status_created", "aml_cases", ["status", "created_at"]
    )
    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_assistant_messages_customer_id_customers",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_assistant_messages_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assistant_messages"),
    )
    op.create_index(
        "ix_assistant_messages_user_id", "assistant_messages", ["user_id"]
    )
    op.create_index(
        "ix_assistant_messages_customer_id", "assistant_messages", ["customer_id"]
    )
    op.create_index(
        "ix_assistant_messages_user_customer_created",
        "assistant_messages",
        ["user_id", "customer_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_assistant_messages_user_customer_created",
        table_name="assistant_messages",
    )
    op.drop_index("ix_assistant_messages_customer_id", table_name="assistant_messages")
    op.drop_index("ix_assistant_messages_user_id", table_name="assistant_messages")
    op.drop_table("assistant_messages")
    op.drop_index("ix_aml_cases_status_created", table_name="aml_cases")
    op.drop_index("ix_aml_cases_transaction_id", table_name="aml_cases")
    op.drop_index("ix_aml_cases_customer_id", table_name="aml_cases")
    op.drop_table("aml_cases")
    op.drop_table("aml_rules")
    op.drop_constraint("valid_status", "transactions", type_="check")
    op.create_check_constraint(
        "valid_status",
        "transactions",
        "status IN ('pending', 'completed', 'failed', 'reversed', 'rejected')",
    )
