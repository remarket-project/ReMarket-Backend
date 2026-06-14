"""add DISPUTED to orderstatus enum

Revision ID: 20260614_disputed
Revises: cc704ea5d053
Create Date: 2026-06-14 06:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '20260614_disputed'
down_revision = 'cc704ea5d053'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE orderstatus ADD VALUE 'DISPUTED'")


def downgrade():
    # PostgreSQL does not support removing values from enums easily.
    # This would require creating a new type without 'DISPUTED' and migrating.
    pass
