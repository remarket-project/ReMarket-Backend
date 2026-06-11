"""add_reserved_to_listingstatus_enum

Revision ID: cfd76146ebdd
Revises: 2899f34aca4a
Create Date: 2026-06-10 16:13:21.263487

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'cfd76146ebdd'
down_revision = '2899f34aca4a'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE listingstatus ADD VALUE IF NOT EXISTS 'RESERVED'")


def downgrade():
    # PostgreSQL does not support removing a value from an enum
    # without recreating the type, so downgrade is a no-op
    pass
