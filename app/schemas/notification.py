import uuid
from typing import Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from app.models.enums import NotificationType


class NotificationCreate(BaseModel):
    user_id: uuid.UUID
    type: NotificationType
    title: str = Field(..., max_length=255)
    message: str
    data: Optional[dict[str, Any]] = None


class NotificationRead(NotificationCreate):
    id: uuid.UUID
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
