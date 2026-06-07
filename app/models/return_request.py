"""ReturnRequest model for buyer return/refund requests."""
import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, String
from sqlmodel import Field, SQLModel


class ReturnReason(str, Enum):
    WRONG_ITEM = "wrong_item"
    DEFECTIVE = "defective"
    DAMAGED = "damaged"
    NOT_AS_DESCRIBED = "not_as_described"
    FAKE = "fake"
    NO_LONGER_NEEDED = "no_longer_needed"


class ReturnStatus(str, Enum):
    PENDING = "pending"
    SELLER_APPROVED = "seller_approved"
    SELLER_REJECTED = "seller_rejected"
    AWAITING_RETURN = "awaiting_return"
    RETURN_SHIPPED = "return_shipped"
    RETURN_DELIVERED = "return_delivered"
    REFUNDED = "refunded"
    DISPUTED = "disputed"
    ADMIN_RESOLVED = "admin_resolved"


class ReturnRequest(SQLModel, table=True):
    __tablename__ = "return_requests"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    order_id: uuid.UUID = Field(foreign_key="orders.id", index=True)
    buyer_id: uuid.UUID = Field(foreign_key="users.id")
    seller_id: uuid.UUID = Field(foreign_key="users.id")

    reason: str = Field(sa_column=Column(String(50)))
    description: str | None = Field(default=None, max_length=1000)
    images: str | None = Field(default=None, max_length=2000)

    status: str = Field(default="pending", sa_column=Column(String(50)))

    return_fee: int = Field(default=0)
    refund_amount: int = Field(default=0)

    return_tracking_number: str | None = Field(default=None, max_length=50)
    return_carrier: str | None = Field(default=None, max_length=50)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    seller_responded_at: datetime | None = None
    buyer_shipped_at: datetime | None = None
    seller_received_at: datetime | None = None
    refunded_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    admin_id: uuid.UUID | None = Field(default=None, foreign_key="users.id")
    admin_notes: str | None = Field(default=None, max_length=1000)
    resolution: str | None = Field(default=None, max_length=500)
