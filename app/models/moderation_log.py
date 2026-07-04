"""Moderation log model — records every AI moderation decision."""
import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ModerationLog(SQLModel, table=True):
    __tablename__ = "moderation_logs"  # type: ignore

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    listing_id: uuid.UUID = Field(foreign_key="listings.id", index=True)
    listing_title: str = Field(max_length=500)
    decision: str = Field(max_length=20)
    reason: str | None = Field(default=None, max_length=500)
    model_used: str | None = Field(default=None, max_length=100)
    image_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=now)
