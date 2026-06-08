"""
Dispute schemas for request/response validation.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DisputeCreate(BaseModel):
    """Create dispute request."""
    order_id: uuid.UUID
    reason: str = Field(..., min_length=10, max_length=2000)
    evidence_images: list[str] = Field(default=[], max_length=5)


class DisputeEvidenceRead(BaseModel):
    id: uuid.UUID
    dispute_id: uuid.UUID
    uploaded_by: uuid.UUID
    image_url: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DisputeRead(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    raised_by: uuid.UUID
    reason: str
    status: str
    resolved_by: uuid.UUID | None
    resolution: str | None
    admin_notes: str | None
    created_at: datetime
    resolved_at: datetime | None
    evidence: list[DisputeEvidenceRead] = []

    model_config = {"from_attributes": True}
