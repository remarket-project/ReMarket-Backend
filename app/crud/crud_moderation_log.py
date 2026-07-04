"""CRUD helpers for AI moderation logs."""
import uuid
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.moderation_log import ModerationLog


async def create_moderation_log(
    db: AsyncSession,
    listing_id: uuid.UUID,
    listing_title: str,
    decision: str,
    reason: str | None = None,
    model_used: str | None = None,
    image_count: int = 0,
) -> ModerationLog:
    log = ModerationLog(
        listing_id=listing_id,
        listing_title=listing_title,
        decision=decision,
        reason=reason,
        model_used=model_used,
        image_count=image_count,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def get_moderation_logs(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    decision: str | None = None,
) -> tuple[list[ModerationLog], int]:
    conditions: list[Any] = []
    if decision:
        conditions.append(ModerationLog.decision == decision)

    count_query = select(func.count()).select_from(ModerationLog)
    query = select(ModerationLog)

    if conditions:
        count_query = count_query.where(*conditions)
        query = query.where(*conditions)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(
        query.order_by(desc(ModerationLog.created_at)).offset(skip).limit(limit)  # type: ignore[arg-type]
    )
    return list(result.scalars().all()), total
