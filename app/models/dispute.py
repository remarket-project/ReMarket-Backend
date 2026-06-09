"""
Dispute & DisputeEvidence models for ReMarket.

Tracks buyer/seller disputes with evidence images.
"""
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship

from app.models.base import BaseUUID

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.user import User


class Dispute(BaseUUID, table=True):
    __tablename__ = "disputes" # type: ignore

    order_id: uuid.UUID = Field(foreign_key="orders.id", nullable=False, index=True)
    raised_by: uuid.UUID = Field(foreign_key="users.id", nullable=False)
    reason: str = Field(max_length=2000)
    status: str = Field(default="open")  # open → resolved

    resolved_by: uuid.UUID | None = Field(foreign_key="users.id", default=None)
    resolution: str | None = Field(default=None)  # refund | release | partial_refund
    admin_notes: str | None = Field(default=None, max_length=2000)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = Field(default=None)

    # Relationships
    order: "Order" = Relationship(back_populates="disputes")
    evidence: list["DisputeEvidence"] = Relationship(back_populates="dispute", cascade_delete=True)
    raiser: "User" = Relationship(
        back_populates="disputes_raised",
        sa_relationship_kwargs={"foreign_keys": "Dispute.raised_by"},
    )


class DisputeEvidence(BaseUUID, table=True):
    __tablename__ = "dispute_evidence" # type: ignore

    dispute_id: uuid.UUID = Field(foreign_key="disputes.id", nullable=False)
    uploaded_by: uuid.UUID = Field(foreign_key="users.id", nullable=False)
    image_url: str = Field(max_length=500)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    dispute: "Dispute" = Relationship(back_populates="evidence")
