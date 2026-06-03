"""
Review model for ReMarket.

Handles user reviews and ratings for completed orders.
"""
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

if TYPE_CHECKING:
    from .order import Order
    from .user import User


class Review(SQLModel, table=True):
    """Review database model."""

    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint(
            "order_id", "reviewer_id", name="uq_review_order_reviewer"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    order_id: uuid.UUID = Field(foreign_key="orders.id", ondelete="CASCADE")
    reviewer_id: uuid.UUID = Field(foreign_key="users.id")
    reviewee_id: uuid.UUID = Field(foreign_key="users.id")
    rating: int = Field(ge=1, le=5)
    comment: str | None = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    order: "Order" = Relationship(back_populates="reviews")
    reviewer: "User" = Relationship(
        back_populates="reviews_given",
        sa_relationship_kwargs={"foreign_keys": "Review.reviewer_id"}
    )
    reviewee: "User" = Relationship(
        back_populates="reviews_received",
        sa_relationship_kwargs={"foreign_keys": "Review.reviewee_id"}
    )
