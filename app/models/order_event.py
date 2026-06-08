"""
OrderEvent model: simple event history for orders.
"""
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.order import Order


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class OrderEvent(SQLModel, table=True):
    __tablename__: str = "order_events"  # type: ignore

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    order_id: uuid.UUID = Field(foreign_key="orders.id", index=True)
    event_type: str = Field(max_length=100)
    detail: str | None = Field(default=None, max_length=2000)
    actor_id: uuid.UUID | None = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(
        default_factory=now_utc, sa_column=Column(DateTime(timezone=True))
    )

    # Relationships
    order: Optional["Order"] = Relationship(back_populates="events")
