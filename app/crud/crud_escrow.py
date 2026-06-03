"""
CRUD operations for Escrow.

Handles escrow account management for secure order transactions.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.enums import EscrowStatus
from app.models.escrow import Escrow


async def get_escrow_by_id(
    db: AsyncSession,
    escrow_id: uuid.UUID
) -> Escrow | None:
    """Get escrow by ID."""
    result = await db.execute(
        select(Escrow).where(Escrow.id == escrow_id)
    )
    return result.scalar_one_or_none()


async def get_escrow_by_order_id(
    db: AsyncSession,
    order_id: uuid.UUID
) -> Escrow | None:
    """Get escrow by order ID."""
    result = await db.execute(
        select(Escrow).where(Escrow.order_id == order_id)
    )
    return result.scalar_one_or_none()


async def create_escrow(
    db: AsyncSession,
    order_id: uuid.UUID,
    amount: Decimal,
    buyer_wallet_id: uuid.UUID,
    seller_wallet_id: uuid.UUID
) -> Escrow:
    """
    Create new escrow account.

    Args:
        db: Database session
        order_id: Order ID
        amount: Amount to lock in escrow
        buyer_wallet_id: Buyer wallet ID
        seller_wallet_id: Seller wallet ID

    Returns:
        Created Escrow object
    """
    escrow = Escrow(
        order_id=order_id,
        amount=amount,
        status=EscrowStatus.PENDING.value,
        buyer_wallet_id=buyer_wallet_id,
        seller_wallet_id=seller_wallet_id
    )
    db.add(escrow)
    await db.commit()
    await db.refresh(escrow)
    return escrow


async def fund_escrow(
    db: AsyncSession,
    escrow_id: uuid.UUID
) -> Escrow | None:
    """
    Mark escrow as funded by buyer.

    Args:
        db: Database session
        escrow_id: Escrow ID

    Returns:
        Updated Escrow or None if not found
    """
    result = await db.execute(
        select(Escrow)
        .where(Escrow.id == escrow_id)
        .with_for_update(nowait=False)
    )
    escrow = result.scalar_one_or_none()
    if not escrow:
        return None

    escrow.status = EscrowStatus.FUNDED.value
    escrow.funded_at = datetime.now(timezone.utc)
    escrow.updated_at = datetime.now(timezone.utc)

    db.add(escrow)
    await db.commit()
    await db.refresh(escrow)
    return escrow


async def request_release(
    db: AsyncSession,
    escrow_id: uuid.UUID
) -> Escrow | None:
    """
    Mark escrow as requesting release (buyer received goods).

    Args:
        db: Database session
        escrow_id: Escrow ID

    Returns:
        Updated Escrow or None if not found
    """
    result = await db.execute(
        select(Escrow)
        .where(Escrow.id == escrow_id)
        .with_for_update(nowait=False)
    )
    escrow = result.scalar_one_or_none()
    if not escrow:
        return None

    if escrow.status != EscrowStatus.FUNDED.value:
        raise ValueError(f"Cannot request release from status {escrow.status}")

    escrow.status = EscrowStatus.RELEASE_REQUESTED.value
    escrow.release_requested_at = datetime.now(timezone.utc)
    escrow.updated_at = datetime.now(timezone.utc)

    db.add(escrow)
    await db.commit()
    await db.refresh(escrow)
    return escrow


async def confirm_release(
    db: AsyncSession,
    escrow_id: uuid.UUID
) -> Escrow | None:
    """
    Confirm escrow release (seller received payment).

    Args:
        db: Database session
        escrow_id: Escrow ID

    Returns:
        Updated Escrow or None if not found
    """
    result = await db.execute(
        select(Escrow)
        .where(Escrow.id == escrow_id)
        .with_for_update(nowait=False)
    )
    escrow = result.scalar_one_or_none()
    if not escrow:
        return None

    if escrow.status not in [EscrowStatus.RELEASE_REQUESTED.value, EscrowStatus.FUNDED.value]:
        raise ValueError(f"Cannot confirm release from status {escrow.status}")

    escrow.status = EscrowStatus.RELEASED.value
    escrow.released_at = datetime.now(timezone.utc)
    escrow.updated_at = datetime.now(timezone.utc)

    db.add(escrow)
    await db.commit()
    await db.refresh(escrow)
    return escrow


async def open_dispute(
    db: AsyncSession,
    escrow_id: uuid.UUID,
    reason: str
) -> Escrow | None:
    """
    Open a dispute on escrow.

    Args:
        db: Database session
        escrow_id: Escrow ID
        reason: Dispute reason

    Returns:
        Updated Escrow or None if not found
    """
    result = await db.execute(
        select(Escrow)
        .where(Escrow.id == escrow_id)
        .with_for_update(nowait=False)
    )
    escrow = result.scalar_one_or_none()
    if not escrow:
        return None

    escrow.status = EscrowStatus.DISPUTED.value
    escrow.dispute_reason = reason
    escrow.dispute_opened_at = datetime.now(timezone.utc)
    escrow.updated_at = datetime.now(timezone.utc)

    db.add(escrow)
    await db.commit()
    await db.refresh(escrow)
    return escrow


async def refund_escrow(
    db: AsyncSession,
    escrow_id: uuid.UUID
) -> Escrow | None:
    """
    Refund escrow (return funds to buyer, close order).

    Args:
        db: Database session
        escrow_id: Escrow ID

    Returns:
        Updated Escrow or None if not found
    """
    result = await db.execute(
        select(Escrow)
        .where(Escrow.id == escrow_id)
        .with_for_update(nowait=False)
    )
    escrow = result.scalar_one_or_none()
    if not escrow:
        return None

    escrow.status = EscrowStatus.REFUNDED.value
    escrow.updated_at = datetime.now(timezone.utc)

    db.add(escrow)
    await db.commit()
    await db.refresh(escrow)
    return escrow


async def update_escrow_status(
    db: AsyncSession,
    escrow_id: uuid.UUID,
    new_status: EscrowStatus,
) -> Escrow | None:
    """Update escrow status (for auto-release worker)."""
    result = await db.execute(
        select(Escrow)
        .where(Escrow.id == escrow_id)
        .with_for_update(nowait=False)
    )
    escrow = result.scalar_one_or_none()
    if not escrow:
        return None
    escrow.status = new_status.value
    escrow.updated_at = datetime.now(timezone.utc)
    db.add(escrow)
    await db.commit()
    await db.refresh(escrow)
    return escrow


async def set_delivered(
    db: AsyncSession,
    escrow_id: uuid.UUID,
    delivered_at: datetime | None = None,
) -> Escrow | None:
    """Mark escrow as delivered (GHN webhook). Sets auto-release timer."""
    from app.services.escrow_worker import schedule_auto_release
    result = await db.execute(
        select(Escrow)
        .where(Escrow.id == escrow_id)
        .with_for_update(nowait=False)
    )
    escrow = result.scalar_one_or_none()
    if not escrow:
        return None
    escrow.delivered_at = delivered_at or datetime.now(timezone.utc)
    schedule_auto_release(escrow)
    escrow.updated_at = datetime.now(timezone.utc)
    db.add(escrow)
    await db.commit()
    await db.refresh(escrow)
    return escrow


async def get_disputed_escrows(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20
) -> tuple[list[Escrow], int]:
    """
    Get all disputed escrows (admin view).

    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum records to return

    Returns:
        Tuple of (escrows list, total count)
    """
    # Count total
    count_result = await db.execute(
        select(func.count())
        .select_from(Escrow)
        .where(Escrow.status == EscrowStatus.DISPUTED.value)
    )
    total = count_result.scalar_one()

    # Get escrows
    result = await db.execute(
        select(Escrow)
        .where(Escrow.status == EscrowStatus.DISPUTED.value)
        .order_by(Escrow.dispute_opened_at.desc())
        .offset(skip)
        .limit(limit)
    )
    escrows = list(result.scalars().all())

    return escrows, total


async def resolve_dispute(
    db: AsyncSession,
    escrow_id: uuid.UUID,
    admin_id: uuid.UUID,
    resolution: str,  # "refund" or "release"
    note: str | None = None,
) -> Escrow | None:
    """
    Resolve a disputed escrow.

    Args:
        db: Database session
        escrow_id: Escrow ID
        admin_id: Admin user ID
        resolution: "refund" to refund buyer, "release" to release to seller

    Returns:
        Updated Escrow or None if not found
    """
    result = await db.execute(
        select(Escrow)
        .where(Escrow.id == escrow_id)
        .with_for_update(nowait=False)
    )
    escrow = result.scalar_one_or_none()
    if not escrow:
        return None

    if escrow.status != EscrowStatus.DISPUTED.value:
        raise ValueError(f"Escrow is not disputed, status: {escrow.status}")

    escrow.admin_resolved_by = admin_id
    escrow.admin_notes = note or None
    escrow.resolution_reason = resolution
    escrow.resolved_at = datetime.now(timezone.utc)
    escrow.updated_at = datetime.now(timezone.utc)

    if resolution == "refund":
        escrow.status = EscrowStatus.REFUNDED.value
    elif resolution == "release":
        escrow.status = EscrowStatus.RELEASED.value
    else:
        raise ValueError(f"Invalid resolution: {resolution}")

    db.add(escrow)
    await db.commit()
    await db.refresh(escrow)
    return escrow
