import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pydantic import BaseModel, Field, computed_field

from app.core.config import settings
from app.models.enums import OfferStatus, PaymentMethod
from app.schemas.order import ShippingAddressInput


class OfferBase(BaseModel):
    offer_price: Decimal = Field(..., gt=Decimal("0"), decimal_places=2,
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
    order_id: uuid.UUID | None = None
    last_action_by: uuid.UUID | None = None

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def expires_at(self) -> datetime | None:
        """Thời gian hết hạn xác nhận (chỉ có ý nghĩa khi status = ACCEPTED)."""
        if self.status == OfferStatus.ACCEPTED:
            return self.created_at.replace(tzinfo=timezone.utc) + timedelta(hours=settings.OFFER_CONFIRM_HOURS)
        return None


class OfferStatusUpdate(BaseModel):
    status: OfferStatus = Field(
        ..., description="New status for the offer (ACCEPTED, REJECTED, COUNTERED)")
    offer_price: Decimal | None = Field(
        default=None, gt=Decimal("0"), decimal_places=2)


class OfferConfirmRequest(BaseModel):
    shipping_address: ShippingAddressInput | None = Field(
        default=None, description="Thông tin giao hàng")
    payment_method: PaymentMethod = Field(
        default=PaymentMethod.WALLET, description="Phương thức thanh toán")


class OfferReadWithDetails(OfferRead):
    """Offer with buyer and listing info for frontend display"""
    buyer_name: str | None = None
    listing_title: str | None = None
    listing_price: Decimal | None = None
    listing_negotiable: bool | None = None

    model_config = {"from_attributes": True}
