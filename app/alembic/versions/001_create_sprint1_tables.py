"""
Create Sprint 1 tables (User, Category).

Revision ID: 001
Revises: None
Create Date: 2026-03-19
"""
import sqlalchemy as sa
import sqlmodel
from alembic import op


# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create Sprint 1 tables."""
    # ========================================================================
    # Create users table
    # ========================================================================
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("hashed_refresh_token", sa.String(
            length=255), nullable=True),
        sa.Column("avatar_url", sa.String(), nullable=True),
        sa.Column("bio", sa.String(), nullable=True),
        sa.Column("province", sa.String(length=100), nullable=True),
        sa.Column("district", sa.String(length=100), nullable=True),
        sa.Column("ward", sa.String(length=100), nullable=True),
        sa.Column("address_detail", sa.String(length=255), nullable=True),
        sa.Column("is_phone_verified", sa.Boolean(),
                  nullable=False, server_default="false"),
        sa.Column("is_email_verified", sa.Boolean(),
                  nullable=False, server_default="false"),
        sa.Column("trust_score", sa.DECIMAL(precision=5, scale=1),
                  nullable=False, server_default="0.0"),
        sa.Column("rating_avg", sa.DECIMAL(precision=3, scale=2),
                  nullable=False, server_default="0.00"),
        sa.Column("rating_count", sa.Integer(),
                  nullable=False, server_default="0"),
        sa.Column("completed_orders", sa.Integer(),
                  nullable=False, server_default="0"),
        sa.Column("role", sa.String(length=20),
                  nullable=False, server_default="'user'"),
        sa.Column("is_active", sa.Boolean(),
                  nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="user_email_constraint"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # ========================================================================
    # Create categories table (with self-reference)
    # ========================================================================
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("icon_url", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="category_slug_constraint"),
    )
    op.create_foreign_key(
        "category_parent_id_fk",
        "categories",
        "categories",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL"
    )


def downgrade():
    """Drop Sprint 1 tables."""
    # Drop constraints first
    op.drop_constraint("category_parent_id_fk",
                       "categories", type_="foreignkey")

    # Drop tables
    op.drop_table("categories")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
