"""CRUD operations for ReturnRequest model."""
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.return_request import ReturnRequest, ReturnStatus


async def get_return_by_id(db: AsyncSession, return_id: uuid.UUID) -> ReturnRequest | None:
    result = await db.execute(
        select(ReturnRequest).where(ReturnRequest.id == return_id)
    )
    return result.scalar_one_or_none()


async def get_return_by_order_id(db: AsyncSession, order_id: uuid.UUID) -> ReturnRequest | None:
    result = await db.execute(
        select(ReturnRequest).where(ReturnRequest.order_id == order_id)
    )
    return result.scalar_one_or_none()


async def get_returns_for_seller(
    db: AsyncSession, seller_id: uuid.UUID, skip: int = 0, limit: int = 20
) -> tuple[list[ReturnRequest], int]:
    from sqlalchemy import func

    count_result = await db.execute(
        select(func.count()).select_from(ReturnRequest).where(ReturnRequest.seller_id == seller_id)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(ReturnRequest)
        .where(ReturnRequest.seller_id == seller_id)
        .order_by(ReturnRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = list(result.scalars().all())
    return items, total


async def get_returns_for_buyer(
    db: AsyncSession, buyer_id: uuid.UUID, skip: int = 0, limit: int = 20
) -> tuple[list[ReturnRequest], int]:
    from sqlalchemy import func

    count_result = await db.execute(
        select(func.count()).select_from(ReturnRequest).where(ReturnRequest.buyer_id == buyer_id)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(ReturnRequest)
        .where(ReturnRequest.buyer_id == buyer_id)
        .order_by(ReturnRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = list(result.scalars().all())
    return items, total


async def get_all_returns(
    db: AsyncSession, skip: int = 0, limit: int = 20
) -> tuple[list[ReturnRequest], int]:
    from sqlalchemy import func

    count_result = await db.execute(
        select(func.count()).select_from(ReturnRequest)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(ReturnRequest)
        .order_by(ReturnRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = list(result.scalars().all())
    return items, total


async def get_expired_pending_returns(
    db: AsyncSession, cutoff: datetime
) -> list[ReturnRequest]:
    result = await db.execute(
        select(ReturnRequest).where(
            ReturnRequest.status == ReturnStatus.PENDING.value,
            ReturnRequest.created_at < cutoff,
        )
    )
    return list(result.scalars().all())


async def get_expired_shipping_returns(
    db: AsyncSession, cutoff: datetime
) -> list[ReturnRequest]:
    result = await db.execute(
        select(ReturnRequest).where(
            ReturnRequest.status == ReturnStatus.SELLER_APPROVED.value,
            ReturnRequest.seller_responded_at < cutoff,
        )
    )
    return list(result.scalars().all())
