"""
Escrow model for ReMarket.

Handles escrow accounts for secure order transactions.
Simplified: only tracks financial state (no dispute fields — moved to Dispute table).
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, String
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.order import Order


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


class Escrow(SQLModel, table=True):
    """Escrow account model (simplified)."""

    __tablename__ = "escrows" # type: ignore

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    order_id: uuid.UUID = Field(
        foreign_key="orders.id", ondelete="CASCADE", unique=True, index=True
    )
    amount: Decimal = Field(max_digits=12, decimal_places=2)
    status: str = Field(sa_column=Column(String(50)))

    buyer_wallet_id: uuid.UUID = Field(foreign_key="wallets.id", index=True)
    seller_wallet_id: uuid.UUID = Field(foreign_key="wallets.id", index=True)

    # Timestamps
    funded_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True)) # type: ignore
    released_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True)) # type: ignore
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)) # type: ignore
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)) # type: ignore

    # Relationships
    order: Optional["Order"] = Relationship(back_populates="escrow")
