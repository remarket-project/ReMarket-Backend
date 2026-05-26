import uuid
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from app.models.enums import ConditionGrade, ListingStatus


class ListingBase(BaseModel):
    title: str = Field(..., max_length=500, min_length=5)
    description: Optional[str] = None
    price: Decimal = Field(..., decimal_places=2)
    is_negotiable: bool = True
    condition_grade: ConditionGrade
    category_id: uuid.UUID


class ListingCreate(ListingBase):
    pass


class ListingUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500, min_length=5)
    description: Optional[str] = None
    price: Optional[Decimal] = None
    is_negotiable: Optional[bool] = None
    condition_grade: Optional[ConditionGrade] = None
    category_id: Optional[uuid.UUID] = None
    status: Optional[ListingStatus] = None


class ListingRead(ListingBase):
    id: uuid.UUID
    seller_id: uuid.UUID
    status: ListingStatus
    rejection_reason: Optional[str] = None
    view_count: int = 0
    save_count: int = 0
    is_featured: bool = False
    published_at: Optional[datetime] = None
    location_summary: Optional[str] = None
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
    images: List[ListingImageRead] = []
    seller_name: Optional[str] = None
    seller_avatar_url: Optional[str] = None

    model_config = {"from_attributes": True}


class ListingPaginated(BaseModel):
    """Response schema for paginated listings"""
    items: List[ListingWithImages] = []
    total: int
    skip: int
    limit: int

    model_config = {"from_attributes": True}
