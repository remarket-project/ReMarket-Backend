"""
Order model for ReMarket.

Handles completed purchases, tracking buyer, seller, and transaction details.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Column, String
from sqlmodel import Field, Relationship, SQLModel

from .enums import OrderStatus

if TYPE_CHECKING:
    from .listing import Listing
    from .user import User
    from .review import Review
    from .escrow import Escrow


class Order(SQLModel, table=True):
    """Order database model."""

    __tablename__ = "orders"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    buyer_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    seller_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    listing_id: uuid.UUID = Field(
        foreign_key="listings.id", ondelete="CASCADE")
    final_price: Decimal = Field(decimal_places=2, max_digits=12)
    status: OrderStatus = Field(
        default=OrderStatus.PENDING, sa_column=Column(String(50))
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    buyer: "User" = Relationship(
        back_populates="orders_as_buyer",
        sa_relationship_kwargs={"foreign_keys": "Order.buyer_id"}
    )
    seller: "User" = Relationship(
        back_populates="orders_as_seller",
        sa_relationship_kwargs={"foreign_keys": "Order.seller_id"}
    )
    listing: "Listing" = Relationship(back_populates="orders")
    reviews: list["Review"] = Relationship(
        back_populates="order", cascade_delete=True
    )
    escrow: "Escrow" = Relationship(back_populates="order")
