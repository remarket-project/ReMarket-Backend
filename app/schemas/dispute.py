"""
Dispute schemas for request/response validation.
"""
import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from app.core.config import settings


def _serve_url(image_url: str) -> str:
    """Convert MinIO URL to backend proxy URL."""
    # Find the object path after the bucket name
    bucket = settings.MINIO_BUCKET_NAME or "listings"
    match = re.search(rf"/{bucket}/(.+?)(?:\?|$)", image_url)
    if match:
        path = match.group(1)
        return f"{settings.API_V1_STR}/upload/{path}"
    return image_url


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

    @computed_field
    @property
    def serve_url(self) -> str:
        return _serve_url(self.image_url)


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
