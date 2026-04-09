"""
Escrow model for ReMarket.

Handles escrow accounts for secure order transactions.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, String, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.wallet import Wallet
    from app.models.user import User


def get_datetime_utc() -> datetime:
    """Get current datetime in UTC."""
    return datetime.now(timezone.utc)


# ============================================================================
# Database Model
# ============================================================================

class Escrow(SQLModel, table=True):
    """Escrow account model."""

    __tablename__ = "escrows"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    order_id: uuid.UUID = Field(
        foreign_key="orders.id",
        ondelete="CASCADE",
        unique=True,
        index=True
    )

    amount: Decimal = Field(
        max_digits=12,
        decimal_places=2,
        description="Amount locked in escrow"
    )
    status: str = Field(
        sa_column=Column(String(50)),
        description="Escrow status"
    )

    buyer_wallet_id: uuid.UUID = Field(
        foreign_key="wallets.id",
        index=True
    )
    seller_wallet_id: uuid.UUID = Field(
        foreign_key="wallets.id",
        index=True
    )

    # Dispute information
    dispute_reason: Optional[str] = Field(default=None, max_length=500)
    dispute_opened_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True)
    )
    admin_resolved_by: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="users.id",
        ondelete="SET NULL"
    )

    # Timestamps
    funded_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True)
    )
    release_requested_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True)
    )
    released_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True)
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    # Relationships
    order: Optional["Order"] = Relationship(back_populates="escrow")
