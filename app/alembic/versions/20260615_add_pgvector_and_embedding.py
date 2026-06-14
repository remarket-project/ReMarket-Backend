"""add pgvector extension and embedding column to listings

Revision ID: 20260615_pgvector
Revises: 20260614_disputed
Create Date: 2026-06-15 06:00:00.000000

"""
from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision = '20260615_pgvector'
down_revision = '20260614_disputed'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("listings", sa.Column("embedding", Vector(384), nullable=True))


def downgrade():
    op.drop_column("listings", "embedding")
