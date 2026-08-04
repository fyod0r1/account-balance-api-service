"""create initial schema

Revision ID: 202608030001
Revises:
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202608030001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = sa.Enum("USER", "ADMIN", name="user_role")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_accounts_user_id", "accounts", ["user_id"])

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.String(length=64), nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_payments_transaction_id", "payments", ["transaction_id"], unique=True)
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_account_id", "payments", ["account_id"])

    op.bulk_insert(
        sa.table(
            "users",
            sa.column("id", sa.Integer()),
            sa.column("email", sa.String()),
            sa.column("full_name", sa.String()),
            sa.column("password_hash", sa.String()),
            sa.column("role", user_role),
        ),
        [
            {
                "id": 1,
                "email": "user@example.com",
                "full_name": "Test User",
                "password_hash": (
                    "pbkdf2_sha256$210000$0Z/aIMyO6/X/5PCyLHOv2Q==$"
                    "SUdKfcO3KHX0Rx/CYXQNAxsceXLJkRDIb3fRtbgcU+g="
                ),
                "role": "USER",
            },
            {
                "id": 2,
                "email": "admin@example.com",
                "full_name": "Test Admin",
                "password_hash": (
                    "pbkdf2_sha256$210000$QusKIHHz1WLbtIPwZuQSlw==$"
                    "VNTY+srzMpRgsbQDxwur/UbXaIfq7MXnOzby8ktpFUM="
                ),
                "role": "ADMIN",
            },
        ],
    )
    op.bulk_insert(
        sa.table(
            "accounts",
            sa.column("id", sa.Integer()),
            sa.column("user_id", sa.Integer()),
            sa.column("balance", sa.Numeric(18, 2)),
        ),
        [{"id": 1, "user_id": 1, "balance": 1000}],
    )
    op.execute("SELECT setval('users_id_seq', (SELECT MAX(id) FROM users))")
    op.execute("SELECT setval('accounts_id_seq', (SELECT MAX(id) FROM accounts))")


def downgrade() -> None:
    op.drop_index("ix_payments_account_id", table_name="payments")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_index("ix_payments_transaction_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_accounts_user_id", table_name="accounts")
    op.drop_table("accounts")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    user_role.drop(op.get_bind(), checkfirst=True)
