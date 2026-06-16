"""add_moderation_log

Revision ID: 8745f8284e98
Revises: 20260615_hnsw
Create Date: 2026-06-16 11:05:39.729567

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision = '8745f8284e98'
down_revision = '20260615_hnsw'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('moderation_logs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('listing_id', sa.Uuid(), nullable=False),
        sa.Column('listing_title', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
        sa.Column('decision', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column('reason', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column('model_used', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
        sa.Column('image_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['listing_id'], ['listings.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_moderation_logs_listing_id'), 'moderation_logs', ['listing_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_moderation_logs_listing_id'), table_name='moderation_logs')
    op.drop_table('moderation_logs')
