import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import OrderStatus, PaymentMethod


class OrderBase(BaseModel):
    final_price: Decimal = Field(..., gt=Decimal("0"), decimal_places=2)


class OrderCreate(OrderBase):
    buyer_id: uuid.UUID
    seller_id: uuid.UUID
    listing_id: uuid.UUID


class ShippingAddressInput(BaseModel):
    name: str = Field(..., max_length=255)
    phone: str = Field(..., max_length=20)
    province: str = Field(..., max_length=100)
    district: str = Field(..., max_length=100)
    ward: str = Field(..., max_length=100)
    address_detail: str = Field(..., max_length=255)
    note: str | None = None
    province_id: int | None = None
    district_id: int | None = None
    ward_code: str | None = None


class OrderDirectCreate(BaseModel):
    listing_id: uuid.UUID
    payment_method: PaymentMethod = PaymentMethod.WALLET
    shipping_address: ShippingAddressInput | None = None


class OrderRead(OrderBase):
    id: uuid.UUID
    buyer_id: uuid.UUID
    seller_id: uuid.UUID
    listing_id: uuid.UUID
    status: OrderStatus
    payment_method: PaymentMethod = PaymentMethod.WALLET
    shipping_provider: str | None = None
    shipping_service_type: int | None = None
    shipping_fee: Decimal | None = None
    tracking_number: str | None = None
    expected_delivery_at: datetime | None = None
    delivered_at: datetime | None = None
    shipping_name: str | None = None
    shipping_phone: str | None = None
    shipping_province: str | None = None
    shipping_district: str | None = None
    shipping_ward: str | None = None
    shipping_address_detail: str | None = None
    shipping_note: str | None = None
    shipping_province_id: int | None = None
    shipping_district_id: int | None = None
    shipping_ward_code: str | None = None
    offer_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    has_dispute: bool = False

    model_config = {"from_attributes": True}


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
