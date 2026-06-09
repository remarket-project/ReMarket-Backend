"""Background worker: poll GHN for order status updates as fallback."""
import asyncio
import logging

from datetime import datetime, timezone

from sqlmodel import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.enums import OrderStatus
from app.models.order import Order
from app.services import ghn

logger = logging.getLogger(__name__)

STATUS_MAP = {
    "delivered": OrderStatus.DELIVERED,
    "delivery_fail": OrderStatus.DELIVERY_FAILED,
    "return": OrderStatus.RETURNING,
    "returning": OrderStatus.RETURNING,
    "returned": OrderStatus.RETURNED,
    "cancel": OrderStatus.CANCELLED,
}


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
                            OrderStatus.DELIVERY_FAILED,
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
                            order.status = new_status

                            if new_status == OrderStatus.DELIVERED:
                                order.delivered_at = datetime.now(timezone.utc).replace(tzinfo=None)

                            db.add(order)
                            await db.commit()

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
