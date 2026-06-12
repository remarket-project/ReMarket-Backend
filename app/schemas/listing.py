import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import ConditionGrade, ListingStatus


class ListingBase(BaseModel):
    title: str = Field(..., max_length=500, min_length=5)
    description: str | None = None
    price: Decimal = Field(..., decimal_places=2)
    is_negotiable: bool = True
    condition_grade: ConditionGrade
    category_id: uuid.UUID


class ListingCreate(ListingBase):
    location_summary: str | None = None


class ListingUpdate(BaseModel):
    title: str | None = Field(None, max_length=500, min_length=5)
    description: str | None = None
    price: Decimal | None = None
    is_negotiable: bool | None = None
    condition_grade: ConditionGrade | None = None
    category_id: uuid.UUID | None = None
    status: ListingStatus | None = None


class ListingRead(ListingBase):
    id: uuid.UUID
    seller_id: uuid.UUID
    status: ListingStatus
    rejection_reason: str | None = None
    view_count: int = 0
    save_count: int = 0
    is_featured: bool = False
    published_at: datetime | None = None
    location_summary: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ListingWithDetails(ListingRead):
    pass


class ListingImageRead(BaseModel):
    """Response schema for listing images"""
    id: uuid.UUID
    listing_id: uuid.UUID
    image_url: str
    is_primary: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ListingWithImages(ListingRead):
    """Response schema for listing with images"""
    images: list[ListingImageRead] = []
    seller_name: str | None = None
    seller_avatar_url: str | None = None
    seller_location_summary: str | None = None

    model_config = {"from_attributes": True}


class ListingPaginated(BaseModel):
    """Response schema for paginated listings"""
    items: list[ListingWithImages] = []
    total: int
    skip: int
    limit: int

    model_config = {"from_attributes": True}
