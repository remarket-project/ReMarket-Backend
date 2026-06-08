"""CRUD operations for ReturnRequest model."""
import uuid
from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.return_request import ReturnRequest, ReturnStatus


async def get_return_by_id(db: AsyncSession, return_id: uuid.UUID) -> ReturnRequest | None:
    result = await db.execute(
        select(ReturnRequest).where(ReturnRequest.id == return_id)  # type: ignore[arg-type]
    )
    return result.scalar_one_or_none()


async def get_return_by_order_id(db: AsyncSession, order_id: uuid.UUID) -> ReturnRequest | None:
    result = await db.execute(
        select(ReturnRequest).where(ReturnRequest.order_id == order_id)  # type: ignore[arg-type]
    )
    return result.scalar_one_or_none()


async def get_returns_for_seller(
    db: AsyncSession, seller_id: uuid.UUID, skip: int = 0, limit: int = 20
) -> tuple[list[ReturnRequest], int]:
    from sqlalchemy import func

    count_result = await db.execute(
        select(func.count()).select_from(ReturnRequest).where(ReturnRequest.seller_id == seller_id)  # type: ignore[arg-type]
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(ReturnRequest)
        .where(ReturnRequest.seller_id == seller_id)  # type: ignore[arg-type]
        .order_by(desc(ReturnRequest.created_at))
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
        select(func.count()).select_from(ReturnRequest).where(ReturnRequest.buyer_id == buyer_id)  # type: ignore[arg-type]
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(ReturnRequest)
        .where(ReturnRequest.buyer_id == buyer_id)  # type: ignore[arg-type]
        .order_by(desc(ReturnRequest.created_at))
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
        .order_by(desc(ReturnRequest.created_at))
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
            ReturnRequest.status == ReturnStatus.PENDING.value,  # type: ignore[arg-type]
            ReturnRequest.created_at < cutoff,  # type: ignore[operator]
        )
    )
    return list(result.scalars().all())


async def get_expired_shipping_returns(
    db: AsyncSession, cutoff: datetime
) -> list[ReturnRequest]:
    result = await db.execute(
        select(ReturnRequest).where(
            ReturnRequest.status == ReturnStatus.SELLER_APPROVED.value,  # type: ignore[arg-type]
            ReturnRequest.seller_responded_at < cutoff,  # type: ignore[operator]
        )
    )
    return list(result.scalars().all())
