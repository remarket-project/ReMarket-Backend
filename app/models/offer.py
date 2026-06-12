"""
Offer model for ReMarket.

Handles negotiation offers between buyers and sellers.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Column, Index, String, text
from sqlmodel import Field, Relationship, SQLModel

from .enums import OfferStatus

if TYPE_CHECKING:
    from .listing import Listing
    from .user import User


class Offer(SQLModel, table=True):
    """Offer/negotiation database model."""

    __tablename__ = "offers" # type: ignore

    __table_args__ = (
        Index(
            "uq_offer_active_per_buyer_listing",
            "buyer_id",
            "listing_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'countered')"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    listing_id: uuid.UUID = Field(
        foreign_key="listings.id", ondelete="CASCADE", index=True)
    buyer_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    offer_price: Decimal = Field(decimal_places=2, max_digits=12)
    status: OfferStatus = Field(
        default=OfferStatus.PENDING, sa_column=Column(String(50), index=True)
    )
    order_id: uuid.UUID | None = Field(
        default=None, foreign_key="orders.id", ondelete="SET NULL", nullable=True
    )
    last_action_by: uuid.UUID | None = Field(
        default=None, foreign_key="users.id", nullable=True
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    listing: "Listing" = Relationship(back_populates="offers")
    buyer: "User" = Relationship(
        back_populates="offers_made",
        sa_relationship_kwargs={"foreign_keys": "Offer.buyer_id"},
    )
