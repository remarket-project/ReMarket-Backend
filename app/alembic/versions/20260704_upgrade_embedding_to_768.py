"""Upgrade embedding dimension from 384 to 768

Revision ID: 20260704_emb768
Revises: 20260615_hnsw
Create Date: 2026-07-04

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "20260704_emb768"
down_revision = ("20260615_hnsw", "9baa8bc50936")
branch_labels = None
depends_on = None


def upgrade():
    # Drop HNSW indexes
    op.execute("DROP INDEX IF EXISTS idx_listings_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS idx_faq_chunks_embedding_hnsw")

    # Drop old embedding columns
    op.drop_column("listings", "embedding")
    op.drop_column("faq_chunks", "embedding")

    # Add new 768-dim columns
    op.add_column("listings", sa.Column("embedding", Vector(768)))
    op.add_column("faq_chunks", sa.Column("embedding", Vector(768)))

    # Re-create HNSW indexes
    op.execute(
        "CREATE INDEX idx_listings_embedding_hnsw "
        "ON listings USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 200)"
    )
    op.execute(
        "CREATE INDEX idx_faq_chunks_embedding_hnsw "
        "ON faq_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 200)"
    )


def downgrade():
    # Drop 768-dim indexes and columns
    op.execute("DROP INDEX IF EXISTS idx_listings_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS idx_faq_chunks_embedding_hnsw")

    op.drop_column("listings", "embedding")
    op.drop_column("faq_chunks", "embedding")

    # Restore original 384-dim columns
    op.add_column("listings", sa.Column("embedding", Vector(384)))
    op.add_column("faq_chunks", sa.Column("embedding", Vector(384)))

    op.execute(
        "CREATE INDEX idx_listings_embedding_hnsw "
        "ON listings USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 200)"
    )
    op.execute(
        "CREATE INDEX idx_faq_chunks_embedding_hnsw "
        "ON faq_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 200)"
    )
