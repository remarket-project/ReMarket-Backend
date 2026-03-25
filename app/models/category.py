"""
Category model for ReMarket.

Handles product categories using a tree structure (parent_id).
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.listing import Listing


def get_datetime_utc() -> datetime:
    """Get current datetime in UTC."""
    return datetime.now(timezone.utc)


# ============================================================================
# Base Classes
# ============================================================================

class CategoryBase(SQLModel):
    """Shared category properties."""
    name: str = Field(max_length=255)
    slug: str = Field(unique=True, index=True, max_length=255)
    icon_url: str | None = None


# ============================================================================
# Request Models
# ============================================================================

class CategoryCreate(CategoryBase):
    """Request body for creating a category."""
    parent_id: uuid.UUID | None = Field(
        default=None, description="Parent category ID for subcategories")


class CategoryUpdate(SQLModel):
    """Request body for updating a category."""
    name: str | None = Field(default=None, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    icon_url: str | None = None


# ============================================================================
# Database Model
# ============================================================================

class Category(CategoryBase, table=True):
    """Category database model."""

    __tablename__ = "categories"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    parent_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="categories.id",
        description="Parent category for hierarchical structure"
    )

    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    # Relationships
    parent: Optional["Category"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs=dict(remote_side="Category.id")
    )
    children: list["Category"] = Relationship(back_populates="parent")
    listings: list["Listing"] = Relationship(back_populates="category")


# ============================================================================
# Response Models
# ============================================================================

class CategoryPublic(CategoryBase):
    """Category API response (basic)."""
    id: uuid.UUID
    parent_id: uuid.UUID | None = None
    created_at: datetime


class CategoryWithChildren(CategoryBase):
    """Category with child categories (for tree structure)."""
    id: uuid.UUID
    parent_id: uuid.UUID | None = None
    created_at: datetime
    children: list["CategoryWithChildren"] = []


class CategoriesPublic(SQLModel):
    """Response body for listing categories."""
    data: list[CategoryPublic]
    count: int
