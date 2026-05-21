"""
OrderEvent model: simple event history for orders.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, String
from sqlmodel import Field, SQLModel


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class OrderEvent(SQLModel, table=True):
    __tablename__ = "order_events"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    order_id: uuid.UUID = Field(foreign_key="orders.id", index=True)
    event_type: str = Field(sa_column=String(100))
    detail: Optional[str] = Field(default=None, max_length=2000)
    actor_id: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(
        default_factory=now_utc, sa_type=DateTime(timezone=True))
