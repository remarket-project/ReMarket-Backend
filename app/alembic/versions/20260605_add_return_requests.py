"""add_return_requests_table

Revision ID: 20260605_return
Revises: 20260602_add_stripe
Create Date: 2026-06-05 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel
import uuid


revision = "20260605_return"
down_revision = "20260602_add_stripe"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "return_requests",
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True, default=uuid.uuid4),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column("seller_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("images", sa.String(2000), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("return_fee", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("refund_amount", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("return_tracking_number", sa.String(50), nullable=True),
        sa.Column("return_carrier", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("seller_responded_at", sa.DateTime(), nullable=True),
        sa.Column("buyer_shipped_at", sa.DateTime(), nullable=True),
        sa.Column("seller_received_at", sa.DateTime(), nullable=True),
        sa.Column("refunded_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("admin_id", sa.Uuid(), nullable=True),
        sa.Column("admin_notes", sa.String(1000), nullable=True),
        sa.Column("resolution", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["buyer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seller_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["admin_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_return_requests_order_id", "return_requests", ["order_id"])
    op.create_index("ix_return_requests_buyer_id", "return_requests", ["buyer_id"])
    op.create_index("ix_return_requests_seller_id", "return_requests", ["seller_id"])
    op.create_index("ix_return_requests_status", "return_requests", ["status"])


def downgrade():
    op.drop_table("return_requests")
