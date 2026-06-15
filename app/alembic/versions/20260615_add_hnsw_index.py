"""add HNSW index on listings.embedding and faq_chunks.embedding

Revision ID: 20260615_hnsw
Revises: 20260615_faq
Create Date: 2026-06-15 08:00:00.000000

"""
from alembic import op

revision = '20260615_hnsw'
down_revision = '20260615_faq'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_listings_embedding_hnsw "
        "ON listings USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 200)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_faq_chunks_embedding_hnsw "
        "ON faq_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 200)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_listings_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS idx_faq_chunks_embedding_hnsw")
