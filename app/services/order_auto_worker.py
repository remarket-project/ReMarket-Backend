"""
Auto-complete orders that have been DELIVERED for > auto_complete_hours.

Replaces the old escrow_worker auto-release logic.
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.crud.crud_order import complete_order
from app.crud.crud_notification import create_notification
from app.core.websocket_manager import ws_manager
from app.models.enums import NotificationType
from app.models.order import Order, OrderStatus

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None


async def auto_complete_worker():
    """Check every 60s for DELIVERED orders past auto_complete_at."""
    while True:
        try:
            async with AsyncSessionLocal() as db:
                now = datetime.now(timezone.utc)
                result = await db.execute(
                    select(Order).where(
                        Order.status == OrderStatus.DELIVERED,
                        Order.auto_complete_at.isnot(None),
                        Order.auto_complete_at <= now,
                    )
                )
                orders = list(result.scalars().all())
                for order in orders:
                    await complete_order(db, order)
                    await create_notification(
                        db=db, user_id=order.buyer_id,
                        type=NotificationType.ORDER_AUTO_COMPLETED,
                        title="Đơn hàng tự động hoàn tất",
                        message=f"Đơn hàng #{str(order.id)[:8]} đã tự động hoàn tất sau 48h.",
                    )
                    await create_notification(
                        db=db, user_id=order.seller_id,
                        type=NotificationType.ORDER_AUTO_COMPLETED,
                        title="Đơn hàng tự động hoàn tất",
                        message=f"Đơn hàng #{str(order.id)[:8]} đã tự động hoàn tất. Tiền đã được giải ngân.",
                    )
                    await ws_manager.send_to_user(order.buyer_id, {
                        "type": "order_status_updated",
                        "order_id": str(order.id),
                    })
                    await ws_manager.send_to_user(order.seller_id, {
                        "type": "order_status_updated",
                        "order_id": str(order.id),
                    })
        except Exception as e:
            logger.error("Auto-complete worker error: %s", e)
        await asyncio.sleep(settings.ORDER_AUTO_CHECK_INTERVAL_SECONDS)


def start_auto_worker():
    global _worker_task
    if _worker_task is None:
        _worker_task = asyncio.create_task(auto_complete_worker())
        logger.info("Auto-complete worker started")


def stop_auto_worker():
    global _worker_task
    if _worker_task:
        _worker_task.cancel()
        _worker_task = None
        logger.info("Auto-complete worker stopped")
