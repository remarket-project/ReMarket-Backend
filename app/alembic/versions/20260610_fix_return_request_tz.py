"""fix_return_request_naive_datetime_to_timezone_aware

Revision ID: 20260610_fix_return_tz
Revises: 20260605_return
Create Date: 2026-06-10 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260610_fix_return_tz"
down_revision = "20260605_return"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("return_requests", "created_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column("return_requests", "seller_responded_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="seller_responded_at AT TIME ZONE 'UTC'",
    )
    op.alter_column("return_requests", "buyer_shipped_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="buyer_shipped_at AT TIME ZONE 'UTC'",
    )
    op.alter_column("return_requests", "seller_received_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="seller_received_at AT TIME ZONE 'UTC'",
    )
    op.alter_column("return_requests", "refunded_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="refunded_at AT TIME ZONE 'UTC'",
    )
    op.alter_column("return_requests", "updated_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )


def downgrade():
    op.alter_column("return_requests", "updated_at",
        type_=sa.DateTime(),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )
    op.alter_column("return_requests", "refunded_at",
        type_=sa.DateTime(),
        postgresql_using="refunded_at AT TIME ZONE 'UTC'",
    )
    op.alter_column("return_requests", "seller_received_at",
        type_=sa.DateTime(),
        postgresql_using="seller_received_at AT TIME ZONE 'UTC'",
    )
    op.alter_column("return_requests", "buyer_shipped_at",
        type_=sa.DateTime(),
        postgresql_using="buyer_shipped_at AT TIME ZONE 'UTC'",
    )
    op.alter_column("return_requests", "seller_responded_at",
        type_=sa.DateTime(),
        postgresql_using="seller_responded_at AT TIME ZONE 'UTC'",
    )
    op.alter_column("return_requests", "created_at",
        type_=sa.DateTime(),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
