"""add faq_chunks table

Revision ID: 20260615_faq
Revises: 20260615_pgvector
Create Date: 2026-06-15 07:00:00.000000

"""
from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision = '20260615_faq'
down_revision = '20260615_pgvector'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('faq_chunks',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('question', sa.String(length=500), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(384), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('faq_chunks')
