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
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ListingWithDetails(ListingRead):
    pass
