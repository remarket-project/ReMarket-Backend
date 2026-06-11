"""add_last_action_by_to_offers

Revision ID: 20260611_last_action
Revises: cfd76146ebdd
Create Date: 2026-06-11 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision = "20260611_last_action"
down_revision = "cfd76146ebdd"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("offers", sa.Column("last_action_by", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_offer_last_action_by_user",
        "offers", "users",
        ["last_action_by"], ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("fk_offer_last_action_by_user", "offers", type_="foreignkey")
    op.drop_column("offers", "last_action_by")
