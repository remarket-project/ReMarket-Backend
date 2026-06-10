"""
CRUD operations for Dispute model.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.dispute import Dispute, DisputeEvidence
from app.models.enums import EscrowStatus, ListingStatus, OrderStatus
from app.models.escrow import Escrow
from app.models.listing import Listing
from app.models.order import Order


async def create_dispute(
    db: AsyncSession,
    order_id: uuid.UUID,
    raised_by: uuid.UUID,
    reason: str,
) -> Dispute:
    """Create a new dispute and set order status to DISPUTED."""
    dispute = Dispute(
        order_id=order_id,
        raised_by=raised_by,
        reason=reason,
        status="open",
    )
    db.add(dispute)

    # Set order status to DISPUTED
    order_result = await db.execute(
        select(Order).where(Order.id == order_id).with_for_update()  # type: ignore[arg-type]
    )
    order = order_result.scalar_one_or_none()
    if order and order.status in (OrderStatus.DELIVERED, OrderStatus.SHIPPING):
        order.status = OrderStatus.DISPUTED
        order.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(order)

    await db.commit()
    await db.refresh(dispute)
    return dispute


async def add_evidence(
    db: AsyncSession,
    dispute_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    image_url: str,
) -> DisputeEvidence:
    """Add evidence image to a dispute."""
    evidence = DisputeEvidence(
        dispute_id=dispute_id,
        uploaded_by=uploaded_by,
        image_url=image_url,
    )
    db.add(evidence)
    await db.commit()
    await db.refresh(evidence)
    return evidence


async def get_dispute_by_id(db: AsyncSession, dispute_id: uuid.UUID) -> Dispute | None:
    """Get dispute by ID."""
    result = await db.execute(
        select(Dispute)
        .options(selectinload(Dispute.evidence))
        .where(Dispute.id == dispute_id)  # type: ignore[arg-type]
    )
    return result.scalar_one_or_none()


async def get_dispute_by_order(db: AsyncSession, order_id: uuid.UUID) -> Dispute | None:
    """Get dispute for an order (if exists)."""
    result = await db.execute(
        select(Dispute)
        .options(selectinload(Dispute.evidence))
        .where(Dispute.order_id == order_id)  # type: ignore[arg-type]
    )
    return result.scalar_one_or_none()


async def get_evidence_for_dispute(
    db: AsyncSession, dispute_id: uuid.UUID
) -> list[DisputeEvidence]:
    """Get all evidence images for a dispute."""
    result = await db.execute(
        select(DisputeEvidence).where(DisputeEvidence.dispute_id == dispute_id)  # type: ignore[arg-type]
    )
    return list(result.scalars().all())


async def resolve_dispute(
    db: AsyncSession,
    dispute_id: uuid.UUID,
    resolved_by: uuid.UUID,
    resolution: str,
    admin_notes: str | None = None,
) -> Dispute:
    """
    Resolve a dispute.

    resolution = "release": order → COMPLETED, escrow → RELEASED
    resolution = "refund":  order → RETURNED, escrow → REFUNDED, listing → ACTIVE
    """
    from app.crud.crud_wallet import transfer_locked_to_user, unlock_balance

    result = await db.execute(
        select(Dispute).where(Dispute.id == dispute_id).with_for_update()  # type: ignore[arg-type]
    )
    dispute = result.scalar_one_or_none()
    if not dispute:
        raise ValueError("Dispute not found")

    if dispute.status != "open":
        raise ValueError(f"Dispute is already {dispute.status}")

    dispute.status = "resolved"
    dispute.resolved_by = resolved_by
    dispute.resolution = resolution
    dispute.admin_notes = admin_notes
    dispute.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(dispute)

    # Get order
    order_result = await db.execute(
        select(Order).where(Order.id == dispute.order_id).with_for_update()  # type: ignore[arg-type]
    )
    order = order_result.scalar_one_or_none()

    # Get escrow
    escrow_result = await db.execute(
        select(Escrow).where(Escrow.order_id == dispute.order_id).with_for_update()  # type: ignore[arg-type]
    )
    escrow = escrow_result.scalar_one_or_none()

    if resolution == "release":
        if order:
            order.status = OrderStatus.COMPLETED
            order.updated_at = datetime.now(timezone.utc)
            db.add(order)
        if escrow and escrow.status == EscrowStatus.FUNDED.value:
            await transfer_locked_to_user(
                db=db,
                from_wallet_id=escrow.buyer_wallet_id,
                to_wallet_id=escrow.seller_wallet_id,
                amount=escrow.amount,
                order_id=dispute.order_id,
                description=f"Payment for disputed order {dispute.order_id} (resolved: release)",
            )
            escrow.status = EscrowStatus.RELEASED.value
            escrow.released_at = datetime.now(timezone.utc)
            escrow.updated_at = datetime.now(timezone.utc)
            db.add(escrow)
    elif resolution == "refund":
        if order:
            order.status = OrderStatus.RETURNED
            order.updated_at = datetime.now(timezone.utc)
            db.add(order)
            # Revert listing to ACTIVE
            listing_result = await db.execute(
                select(Listing).where(Listing.id == order.listing_id).with_for_update()  # type: ignore[arg-type]
            )
            listing = listing_result.scalar_one_or_none()
            if listing:
                listing.status = ListingStatus.ACTIVE
                db.add(listing)
        if escrow and escrow.status in ("funded", "disputed"):
            await unlock_balance(
                db=db,
                wallet_id=escrow.buyer_wallet_id,
                amount=escrow.amount,
                order_id=dispute.order_id,
                description=f"Refund for disputed order {dispute.order_id} (resolved: refund)",
            )
            escrow.status = EscrowStatus.REFUNDED.value
            escrow.updated_at = datetime.now(timezone.utc)
            db.add(escrow)
    else:
        raise ValueError(f"Invalid resolution: {resolution}")

    await db.commit()
    await db.refresh(dispute)
    return dispute


async def list_disputes(
    db: AsyncSession,
    status: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Dispute], int]:
    """List disputes with optional status filter."""
    from sqlalchemy import func

    query = select(Dispute).options(selectinload(Dispute.evidence))
    count_query = select(func.count()).select_from(Dispute)

    if status:
        query = query.where(Dispute.status == status)  # type: ignore[arg-type]
        count_query = count_query.where(Dispute.status == status)  # type: ignore[arg-type]

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    result = await db.execute(
        query.order_by(desc(Dispute.created_at)).offset(skip).limit(limit)  # type: ignore[arg-type]
    )
    disputes = list(result.scalars().all())

    return disputes, total
