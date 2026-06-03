"""
Order model for ReMarket.

Handles completed purchases, tracking buyer, seller, and transaction details.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, String
from sqlmodel import Field, Relationship, SQLModel

from .enums import OrderStatus, PaymentMethod

if TYPE_CHECKING:
    from .escrow import Escrow
    from .listing import Listing
    from .review import Review
    from .user import User


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

    # Payment method
    payment_method: PaymentMethod = Field(
        default=PaymentMethod.WALLET, sa_column=Column(String(20))
    )

    # Shipping & Delivery
    shipping_provider: str | None = Field(default=None, max_length=50)
    shipping_service_type: int | None = None
    shipping_fee: Decimal | None = Field(default=None, decimal_places=2, max_digits=12)
    tracking_number: str | None = Field(default=None, max_length=50, index=True)
    expected_delivery_at: datetime | None = None
    delivered_at: datetime | None = None

    # Shipping address (snapshot at time of order)
    shipping_name: str | None = Field(default=None, max_length=255)
    shipping_phone: str | None = Field(default=None, max_length=20)
    shipping_province: str | None = Field(default=None, max_length=100)
    shipping_district: str | None = Field(default=None, max_length=100)
    shipping_ward: str | None = Field(default=None, max_length=100)
    shipping_address_detail: str | None = Field(default=None, max_length=255)
    shipping_note: str | None = Field(default=None, max_length=500)

    # GHN IDs for shipping (dùng khi tạo đơn GHN)
    shipping_province_id: int | None = None
    shipping_district_id: int | None = None
    shipping_ward_code: str | None = Field(default=None, max_length=20)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

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
