"""
CRUD operations for Order model.

Handles order creation, retrieval, and status updates.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.enums import ListingStatus, OfferStatus, OrderStatus
from app.models.listing import Listing
from app.models.offer import Offer
from app.models.order import Order
from app.models.user import User
from app.crud.crud_order_event import create_order_event


def utc_now() -> datetime:
    """Return UTC datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def get_order_by_id(db: AsyncSession, order_id: uuid.UUID) -> Optional[Order]:
    """Get order by ID."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    return result.scalar_one_or_none()


async def get_user_orders(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20
) -> tuple[list[Order], int]:
    """Get paginated orders for a user (as buyer or seller)."""
    from sqlalchemy import func

    base_condition = or_(Order.buyer_id == user_id, Order.seller_id == user_id)

    # Count total
    count_result = await db.execute(
        select(func.count()).select_from(Order).where(base_condition)
    )
    total = count_result.scalar_one()

    # Get paginated items
    result = await db.execute(
        select(Order)
        .where(base_condition)
        .order_by(Order.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = list(result.scalars().all())

    return items, total


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
        .where(Listing.id == listing.id)
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
    locked_listing.status = ListingStatus.SOLD

    # Reject all pending offers on this listing
    result = await db.execute(
        select(Offer)
        .where(
            Offer.listing_id == locked_listing.id,
            Offer.status.in_([OfferStatus.PENDING, OfferStatus.COUNTERED])
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
    """Complete an order and update seller stats."""
    order.status = OrderStatus.COMPLETED
    order.updated_at = utc_now()

    # Update seller's completed_orders count
    await db.execute(
        update(User)
        .where(User.id == order.seller_id)
        .values(completed_orders=User.completed_orders + 1)
    )

    await db.commit()
    await db.refresh(order)
    await create_order_event(db, order.id, "ORDER_COMPLETED", "Order completed", actor_id=order.buyer_id)
    return order


async def cancel_order(db: AsyncSession, order: Order) -> Order:
    """Cancel an order and revert listing to ACTIVE."""
    order.status = OrderStatus.CANCELLED
    order.updated_at = utc_now()

    # Revert listing status to ACTIVE
    await db.execute(
        update(Listing)
        .where(Listing.id == order.listing_id)
        .values(status=ListingStatus.ACTIVE)
    )

    await db.commit()
    await db.refresh(order)
    await create_order_event(db, order.id, "ORDER_CANCELLED", "Order cancelled", actor_id=order.buyer_id)
    return order


async def update_order_status(
    db: AsyncSession,
    order_id: uuid.UUID,
    new_status: OrderStatus
) -> Optional[Order]:
    """Update order status."""
    order = await get_order_by_id(db, order_id)
    if not order:
        return None

    order.status = new_status
    order.updated_at = utc_now()

    db.add(order)
    await db.commit()
    await db.refresh(order)
    await create_order_event(db, order.id, "ORDER_STATUS_UPDATED", f"Status updated to {new_status}")
    return order
