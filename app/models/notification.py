"""
Notification model for ReMarket.

Handles notifications for users about various events.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column, String
from sqlmodel import Field, SQLModel

from .enums import NotificationType


class Notification(SQLModel, table=True):
    """Notification database model."""

    __tablename__ = "notifications" # type: ignore

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    type: NotificationType = Field(sa_column=Column(String(50)))
    title: str = Field(max_length=255)
    message: str
    data: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )
    is_read: bool = Field(default=False, index=True)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
