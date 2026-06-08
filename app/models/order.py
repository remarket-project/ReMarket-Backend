import uuid
from datetime import datetime
from decimal import Decimal

from sqlmodel import Field, Relationship

from app.models.base import BaseUUID
from app.models.enums import OrderStatus, PaymentMethod


class Order(BaseUUID, table=True):
    __tablename__ = "orders"

    buyer_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, index=True)
    seller_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, index=True)
    listing_id: uuid.UUID = Field(foreign_key="listings.id", nullable=False)
    offer_id: uuid.UUID | None = Field(
        default=None, foreign_key="offers.id", nullable=True
    )

    final_price: Decimal = Field(default=0, max_digits=12, decimal_places=2)

    status: OrderStatus = Field(default=OrderStatus.PENDING)
    payment_method: PaymentMethod = Field(default=PaymentMethod.WALLET)

    # Shipping info
    shipping_provider: str | None = None
    shipping_service_type: int | None = None
    shipping_fee: Decimal | None = None
    tracking_number: str | None = None
    expected_delivery_at: datetime | None = None
    delivered_at: datetime | None = None

    # Shipping address (text)
    shipping_name: str | None = None
    shipping_phone: str | None = None
    shipping_province: str | None = None
    shipping_district: str | None = None
    shipping_ward: str | None = None
    shipping_address_detail: str | None = None
    shipping_note: str | None = None

    # Shipping address (GHN IDs)
    shipping_province_id: int | None = None
    shipping_district_id: int | None = None
    shipping_ward_code: str | None = None

    # Auto-complete / dispute timers
    delivered_at_record: datetime | None = None          # Thời gian admin bấm DELIVERED
    auto_complete_at: datetime | None = None             # Tự động COMPLETED sau 48h
    auto_release_at: datetime | None = None              # Tự động RELEASE escrow

    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    updated_at: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        sa_column_kwargs={"onupdate": lambda: datetime.utcnow()},
    )

    # Relationships
    listing: "Listing" = Relationship(back_populates="orders")
    buyer: "User" = Relationship(back_populates="orders_as_buyer")
    seller: "User" = Relationship(back_populates="orders_as_seller")
    events: list["OrderEvent"] = Relationship(back_populates="order")
