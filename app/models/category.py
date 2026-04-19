"""
Category model for ReMarket.

Uses a flat category structure (no parent-child hierarchy).
"""
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

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
    pass


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

    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    # Relationships
    listings: list["Listing"] = Relationship(back_populates="category")


# ============================================================================
# Response Models
# ============================================================================

class CategoryPublic(CategoryBase):
    """Category API response (basic)."""
    id: uuid.UUID
    created_at: datetime


class CategoriesPublic(SQLModel):
    """Response body for listing categories."""
    data: list[CategoryPublic]
    count: int
