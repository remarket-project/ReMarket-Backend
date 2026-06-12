"""merge_heads

Revision ID: 9fe672333c5b
Revises: 20260610_fix_return_tz, 20260611_last_action
Create Date: 2026-06-12 14:01:27.081471

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '9fe672333c5b'
down_revision = ('20260610_fix_return_tz', '20260611_last_action')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
