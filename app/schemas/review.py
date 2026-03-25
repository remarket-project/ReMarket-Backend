import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    order_id: uuid.UUID
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = None


class ReviewRead(ReviewCreate):
    id: uuid.UUID
    reviewer_id: uuid.UUID
    reviewee_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
