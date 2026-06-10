"""Background worker: poll GHN for order status updates as fallback."""
import asyncio
import logging

from datetime import datetime, timedelta, timezone

from sqlalchemy import select as sa_select
from sqlmodel import select

from app.core.config import settings
from app.crud import crud_escrow, crud_order_event
from app.crud.crud_wallet import get_wallet_by_user_id, unlock_balance
from app.db.session import AsyncSessionLocal
from app.models.enums import ListingStatus, OrderStatus
from app.models.listing import Listing
from app.models.order import Order
from app.services import ghn

logger = logging.getLogger(__name__)

STATUS_MAP = {
    "delivered": OrderStatus.DELIVERED,
    "delivery_fail": OrderStatus.RETURNING,
    "return": OrderStatus.RETURNING,
    "returning": OrderStatus.RETURNING,
    "returned": OrderStatus.RETURNED,
    "cancel": OrderStatus.CANCELLED,
}

ESCROW_ACTIONS = {
    OrderStatus.RETURNED: ("refund", True),
    OrderStatus.CANCELLED: ("refund", True),
}


async def _handle_polling_status_change(db, order, new_status):
    """Handle escrow + listing revert when polling detects a status change."""
    order.status = new_status

    if new_status == OrderStatus.DELIVERED:
        order.delivered_at = datetime.now(timezone.utc).replace(tzinfo=None)
        order.delivered_at_record = order.delivered_at
        order.auto_complete_at = order.delivered_at_record + timedelta(
            hours=settings.ORDER_AUTO_COMPLETE_HOURS
        )

    if new_status in ESCROW_ACTIONS:
        action, revert_listing = ESCROW_ACTIONS[new_status]
        escrow = await crud_escrow.get_escrow_by_order_id(db, order.id)

        if action == "refund" and escrow:
            if escrow.status in ("funded", "disputed"):
                buyer_wallet = await get_wallet_by_user_id(db, order.buyer_id)
                if buyer_wallet:
                    await unlock_balance(
                        db, buyer_wallet.id, escrow.amount, order.id,
                        description=f"Refund from GHN poll: {order.tracking_number}",
                    )
                escrow.status = "refunded"
                escrow.updated_at = datetime.now(timezone.utc)
                db.add(escrow)

        if revert_listing:
            listing_result = await db.execute(
                sa_select(Listing).where(Listing.id == order.listing_id).with_for_update()
            )
            listing = listing_result.scalar_one_or_none()
            if listing:
                listing.status = ListingStatus.ACTIVE
                db.add(listing)

    await crud_order_event.create_order_event(
        db, order.id, f"GHN_POLL_{new_status.value}",
        f"GHN poll: {order.tracking_number} -> {new_status}",
        actor_id=None,
    )

    db.add(order)
    await db.commit()


async def poll_ghn_status():
    """Cứ mỗi 300s, check các order đang active."""
    logger.info("GHN polling worker started")
    while True:
        try:
            async with AsyncSessionLocal() as db:
                active_orders = await db.execute(
                    select(Order).where(
                        Order.shipping_provider == "ghn",  # type: ignore[arg-type]
                        Order.tracking_number.is_not(None),  # type: ignore[arg-type]
                        Order.status.in_([  # type: ignore[attr-defined]
                            OrderStatus.SHIPPING,
                            OrderStatus.RETURNING,
                        ]),
                    )
                )
                for order in active_orders.scalars():
                    try:
                        info = await ghn.get_order_info(order.tracking_number)  # type: ignore[arg-type]
                        ghn_status = info.get("status", "").lower()

                        new_status = STATUS_MAP.get(ghn_status)
                        if new_status and new_status.value != order.status.value:
                            logger.info(
                                f"GHN poll: {order.tracking_number} "
                                f"{order.status} -> {new_status}"
                            )
                            await _handle_polling_status_change(db, order, new_status)

                    except Exception as e:
                        logger.warning(
                            f"GHN poll error for {order.tracking_number}: {e}"
                        )
        except Exception as e:
            logger.error(f"GHN polling error: {e}")

        await asyncio.sleep(settings.GHN_POLL_INTERVAL if hasattr(settings, 'GHN_POLL_INTERVAL') else 300)


def start_polling():
    """Start polling worker trong lifespan."""
    task = asyncio.create_task(poll_ghn_status())
    return task
