"""
CRUD operations for Order model.

Handles order creation, retrieval, and status updates.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import desc, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.crud.crud_order_event import create_order_event
from app.models.enums import EscrowStatus, ListingStatus, OfferStatus, OrderStatus
from app.models.escrow import Escrow
from app.models.listing import Listing
from app.models.offer import Offer
from app.models.order import Order
from app.models.user import User


def utc_now() -> datetime:
    """Return UTC datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def get_order_by_id(db: AsyncSession, order_id: uuid.UUID) -> Order | None:
    """Get order by ID."""
    result = await db.execute(select(Order).where(Order.id == order_id))  # type: ignore[arg-type]
    return result.scalar_one_or_none()


async def get_user_orders(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20
) -> tuple[list[Order], int]:
    """Get paginated orders for a user (as buyer or seller)."""
    from sqlalchemy import func

    base_condition = or_(Order.buyer_id == user_id, Order.seller_id == user_id)  # type: ignore[arg-type]

    # Count total
    count_result = await db.execute(
        select(func.count()).select_from(Order).where(base_condition)  # type: ignore[arg-type]
    )
    total = count_result.scalar_one()

    # Get paginated items
    result = await db.execute(
        select(Order)
        .where(base_condition)  # type: ignore[arg-type]
        .order_by(desc(Order.created_at))  # type: ignore[arg-type]
        .offset(skip)
        .limit(limit)
    )
    items = list(result.scalars().all())

    return items, total


async def get_order_by_tracking(
    db: AsyncSession,
    tracking_number: str,
) -> Order | None:
    """Get order by GHN tracking number."""
    result = await db.execute(
        select(Order).where(Order.tracking_number == tracking_number)  # type: ignore[arg-type]
    )
    return result.scalar_one_or_none()


async def create_direct_order(
    db: AsyncSession,
    buyer_id: uuid.UUID,
    listing: Listing
) -> tuple[Order, list[Offer]]:
    """
    Create a direct order (Buy Now) with locking to prevent race conditions.

    Returns:
        tuple: (order, list_of_rejected_offers)

    Raises:
        ValueError: If listing is no longer available
    """
    # Lock the listing to prevent concurrent purchases
    result = await db.execute(
        select(Listing)
        .where(Listing.id == listing.id)  # type: ignore[arg-type]
        .with_for_update(nowait=False)
    )
    locked_listing = result.scalar_one_or_none()

    if not locked_listing:
        raise ValueError("Listing not found")

    # Double-check listing is still available
    if locked_listing.status != ListingStatus.ACTIVE:
        raise ValueError("Listing is no longer available for purchase")

    # Create order
    order = Order(
        buyer_id=buyer_id,
        seller_id=locked_listing.seller_id,
        listing_id=locked_listing.id,
        final_price=locked_listing.price,
        status=OrderStatus.PENDING,
    )
    db.add(order)
    await db.flush()  # Get order.id before commit
    locked_listing.status = ListingStatus.SOLD

    # Reject all pending offers on this listing
    result = await db.execute(
        select(Offer)
        .where(
            Offer.listing_id == locked_listing.id,  # type: ignore[arg-type]
            Offer.status.in_([OfferStatus.PENDING, OfferStatus.COUNTERED]),  # type: ignore[attr-defined]
        )
        .with_for_update()
    )
    rejected_offers = list(result.scalars().all())
    for offer in rejected_offers:
        offer.status = OfferStatus.REJECTED

    await db.commit()
    await db.refresh(order)
    # record timeline event
    await create_order_event(db, order.id, "ORDER_CREATED", f"Order created for listing {locked_listing.id}", actor_id=buyer_id)
    return order, rejected_offers


async def complete_order(db: AsyncSession, order: Order) -> Order:
    """Complete an order, release escrow, and update seller stats.

    FIXED BUG-04: Now also releases escrow if funded.
    """
    from app.crud.crud_wallet import transfer_locked_to_user

    order.status = OrderStatus.COMPLETED
    order.updated_at = utc_now()

    # Update seller's completed_orders count
    await db.execute(
        update(User)
        .where(User.id == order.seller_id)  # type: ignore[arg-type]
        .values(completed_orders=User.completed_orders + 1)
    )

    # Release escrow if funded (BUG-04 fix)
    escrow_result = await db.execute(
        select(Escrow).where(Escrow.order_id == order.id).with_for_update()  # type: ignore[arg-type]
    )
    escrow = escrow_result.scalar_one_or_none()
    if escrow and escrow.status == EscrowStatus.FUNDED.value:
        await transfer_locked_to_user(
            db=db,
            from_wallet_id=escrow.buyer_wallet_id,
            to_wallet_id=escrow.seller_wallet_id,
            amount=escrow.amount,
            order_id=order.id,
            description=f"Payment for completed order {order.id}",
        )
        escrow.status = EscrowStatus.RELEASED.value
        escrow.released_at = utc_now()
        escrow.updated_at = utc_now()
        db.add(escrow)

    await db.commit()
    await db.refresh(order)
    await create_order_event(db, order.id, "ORDER_COMPLETED", "Order completed", actor_id=order.buyer_id)
    return order


async def refund_order(db: AsyncSession, order: Order) -> Order:
    """Refund order: set RETURNED, refund escrow to buyer, revert listing."""
    from app.crud.crud_wallet import unlock_balance

    order.status = OrderStatus.RETURNED
    order.updated_at = utc_now()

    # Refund escrow if FUNDED or DISPUTED
    escrow_result = await db.execute(
        select(Escrow).where(Escrow.order_id == order.id).with_for_update()  # type: ignore[arg-type]
    )
    escrow = escrow_result.scalar_one_or_none()
    if escrow and escrow.status in ("funded", "disputed"):
        await unlock_balance(
            db=db,
            wallet_id=escrow.buyer_wallet_id,
            amount=escrow.amount,
            order_id=order.id,
            description=f"Refund for returned order {order.id}",
        )
        escrow.status = EscrowStatus.REFUNDED.value
        escrow.updated_at = utc_now()
        db.add(escrow)

    # Revert listing to ACTIVE
    listing_result = await db.execute(
        select(Listing).where(Listing.id == order.listing_id).with_for_update()  # type: ignore[arg-type]
    )
    listing = listing_result.scalar_one_or_none()
    if listing:
        listing.status = ListingStatus.ACTIVE
        db.add(listing)

    await db.commit()
    await db.refresh(order)
    await create_order_event(db, order.id, "ORDER_REFUNDED", "Order refunded to buyer")
    return order


async def cancel_order(db: AsyncSession, order: Order) -> Order:
    """Cancel an order, refund escrow if funded, and revert listing to ACTIVE.

    FIXED BUG-03: Now also refunds escrow if funds were locked.
    """
    from app.crud.crud_wallet import unlock_balance

    order.status = OrderStatus.CANCELLED
    order.updated_at = utc_now()

    # Refund escrow if funded (BUG-03 fix)
    escrow_result = await db.execute(
        select(Escrow).where(Escrow.order_id == order.id).with_for_update()  # type: ignore[arg-type]
    )
    escrow = escrow_result.scalar_one_or_none()
    if escrow:
        if escrow.status == EscrowStatus.FUNDED.value:
            await unlock_balance(
                db=db,
                wallet_id=escrow.buyer_wallet_id,
                amount=escrow.amount,
                order_id=order.id,
                description=f"Refund for cancelled order {order.id}",
            )
            escrow.status = EscrowStatus.REFUNDED.value
            escrow.updated_at = utc_now()
            db.add(escrow)
        elif escrow.status == EscrowStatus.PENDING.value:
            # No funds locked yet, just mark as refunded
            escrow.status = EscrowStatus.REFUNDED.value
            escrow.updated_at = utc_now()
            db.add(escrow)

    # Revert listing status to ACTIVE
    listing_result = await db.execute(
        select(Listing).where(Listing.id == order.listing_id).with_for_update()  # type: ignore[arg-type]
    )
    listing = listing_result.scalar_one_or_none()
    if listing:
        listing.status = ListingStatus.ACTIVE
        db.add(listing)

    await db.commit()
    await db.refresh(order)
    await create_order_event(db, order.id, "ORDER_CANCELLED", "Order cancelled", actor_id=order.buyer_id)
    return order


async def update_order_status(
    db: AsyncSession,
    order_id: uuid.UUID,
    new_status: OrderStatus
) -> Order | None:
    """Update order status with FOR UPDATE to prevent race conditions."""
    result = await db.execute(
        select(Order).where(Order.id == order_id).with_for_update()  # type: ignore[arg-type]
    )
    order = result.scalar_one_or_none()
    if not order:
        return None

    order.status = new_status
    order.updated_at = utc_now()

    db.add(order)
    await db.commit()
    await db.refresh(order)
    await create_order_event(db, order.id, "ORDER_STATUS_UPDATED", f"Status updated to {new_status}")
    return order
