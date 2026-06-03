"""add_stripe_fields

Revision ID: 20260602_add_stripe
Revises: d42d9cf0b040
Create Date: 2026-06-02 21:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision = "20260602_add_stripe"
down_revision = "20260523sc01"
branch_labels = None
depends_on = None


def upgrade():
    # users table
    op.add_column(
        "users",
        sa.Column("stripe_account_id", sa.String(255), nullable=True),
    )
    op.create_index("ix_users_stripe_account_id", "users", ["stripe_account_id"])

    op.add_column(
        "users",
        sa.Column(
            "stripe_onboarding_complete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("stripe_account_status", sa.String(50), nullable=True),
    )

    # wallet_transactions table
    op.add_column(
        "wallet_transactions",
        sa.Column("stripe_payment_intent_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "wallet_transactions",
        sa.Column("stripe_transfer_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "wallet_transactions",
        sa.Column("stripe_payout_id", sa.String(255), nullable=True),
    )


def downgrade():
    op.drop_column("wallet_transactions", "stripe_payout_id")
    op.drop_column("wallet_transactions", "stripe_transfer_id")
    op.drop_column("wallet_transactions", "stripe_payment_intent_id")
    op.drop_column("users", "stripe_account_status")
    op.drop_column("users", "stripe_onboarding_complete")
    op.drop_index("ix_users_stripe_account_id", table_name="users")
    op.drop_column("users", "stripe_account_id")
