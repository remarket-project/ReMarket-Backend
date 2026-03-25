import uuid
from decimal import Decimal
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
from app.models.enums import OfferStatus


class OfferBase(BaseModel):
    offer_price: Decimal = Field(..., gt=0, decimal_places=2,
                                 description="The price offered by the buyer")


class OfferCreate(OfferBase):
    listing_id: uuid.UUID = Field(...,
                                  description="The listing ID to make an offer on")


class OfferRead(OfferBase):
    id: uuid.UUID
    listing_id: uuid.UUID
    buyer_id: uuid.UUID
    status: OfferStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OfferStatusUpdate(BaseModel):
    status: OfferStatus = Field(
        ..., description="New status for the offer (ACCEPTED, REJECTED, COUNTERED)")
    offer_price: Optional[Decimal] = Field(
        default=None, gt=0, decimal_places=2)


class OfferReadWithDetails(OfferRead):
    """Offer with buyer and listing info for frontend display"""
    buyer_name: Optional[str] = None
    listing_title: Optional[str] = None
    listing_price: Optional[Decimal] = None
    listing_negotiable: Optional[bool] = None

    model_config = {"from_attributes": True}
