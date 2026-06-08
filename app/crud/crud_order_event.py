"""CRUD for OrderEvent model."""
import uuid

from sqlalchemy import asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.order_event import OrderEvent


async def create_order_event(
    db: AsyncSession,
    order_id: uuid.UUID,
    event_type: str,
    detail: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> OrderEvent:
    ev = OrderEvent(order_id=order_id, event_type=event_type,
                    detail=detail, actor_id=actor_id)
    db.add(ev)
    await db.commit()
    await db.refresh(ev)
    return ev


async def get_order_events(db: AsyncSession, order_id: uuid.UUID):
    result = await db.execute(select(OrderEvent).where(OrderEvent.order_id == order_id).order_by(asc(OrderEvent.created_at)))  # type: ignore[arg-type]
    return list(result.scalars().all())
