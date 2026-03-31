"""
User schemas for API endpoints.

Handles user profile requests/responses.
"""
from sqlmodel import SQLModel
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime

from app.models import UserPrivate, UserPublic, UserUpdate


class UserMe(BaseModel):
    """Current user profile response"""
    id: uuid.UUID
    email: str
    full_name: str
    phone: Optional[str] = None
    is_active: bool
    is_email_verified: bool
    role: str
    avatar_url: Optional[str] = None
    rating_avg: float = 0.0
    rating_count: int = 0
    trust_score: float = 0.0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserStatusUpdate(BaseModel):
    """Update user status"""
    is_active: bool


# Re-export commonly used schemas
__all__ = ["UserPrivate", "UserPublic",
           "UserUpdate", "UserMe", "UserStatusUpdate"]
