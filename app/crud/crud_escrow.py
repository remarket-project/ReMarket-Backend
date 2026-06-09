"""
CRUD operations for Escrow.

Handles escrow account management for secure order transactions.
Simplified: removed dispute and auto-release functions (moved to Dispute + Order).
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.enums import EscrowStatus
from app.models.escrow import Escrow


async def get_escrow_by_id(db: AsyncSession, escrow_id: uuid.UUID) -> Escrow | None:
    """Get escrow by ID."""
    result = await db.execute(select(Escrow).where(Escrow.id == escrow_id))  # type: ignore[arg-type]
    return result.scalar_one_or_none()


async def get_escrow_by_order_id(db: AsyncSession, order_id: uuid.UUID) -> Escrow | None:
    """Get escrow by order ID."""
    result = await db.execute(select(Escrow).where(Escrow.order_id == order_id))  # type: ignore[arg-type]
    return result.scalar_one_or_none()


async def create_escrow(
    db: AsyncSession,
    order_id: uuid.UUID,
    amount: Decimal,
    buyer_wallet_id: uuid.UUID,
    seller_wallet_id: uuid.UUID
) -> Escrow:
    """Create new escrow account."""
    escrow = Escrow(
        order_id=order_id,
        amount=amount,
        status=EscrowStatus.PENDING.value,
        buyer_wallet_id=buyer_wallet_id,
        seller_wallet_id=seller_wallet_id,
    )
    db.add(escrow)
    await db.commit()
    await db.refresh(escrow)
    return escrow


async def fund_escrow(db: AsyncSession, escrow_id: uuid.UUID) -> Escrow | None:
    """Mark escrow as funded by buyer."""
    result = await db.execute(
        select(Escrow).where(Escrow.id == escrow_id).with_for_update(nowait=False)  # type: ignore[arg-type]
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


async def refund_escrow(db: AsyncSession, escrow_id: uuid.UUID) -> Escrow | None:
    """Refund escrow (return funds to buyer)."""
    result = await db.execute(
        select(Escrow).where(Escrow.id == escrow_id).with_for_update(nowait=False)  # type: ignore[arg-type]
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
