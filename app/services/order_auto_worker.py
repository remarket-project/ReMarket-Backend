"""
Auto-complete orders that have been DELIVERED for > auto_complete_hours.

Replaces the old escrow_worker auto-release logic.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.crud.crud_order import complete_order, cancel_order
from app.crud.crud_notification import create_notification
from app.core.websocket_manager import ws_manager
from app.models.enums import NotificationType
from app.models.order import Order, OrderStatus

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None
_cancel_worker_task: asyncio.Task | None = None


async def auto_complete_worker():
    """Check every 60s for DELIVERED orders past auto_complete_at."""
    while True:
        try:
            async with AsyncSessionLocal() as db:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                result = await db.execute(
                    select(Order).where(
                        Order.status == OrderStatus.DELIVERED,  # type: ignore[arg-type]
                        Order.auto_complete_at.isnot(None),  # type: ignore[arg-type]
                        Order.auto_complete_at <= now,  # type: ignore[operator]
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


async def auto_cancel_pending_worker():
    """Check every 60s for PENDING orders older than auto_cancel_hours."""
    while True:
        try:
            async with AsyncSessionLocal() as db:
                cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=settings.ORDER_AUTO_CANCEL_HOURS)
                result = await db.execute(
                    select(Order).where(
                        Order.status == OrderStatus.PENDING,  # type: ignore[arg-type]
                        Order.created_at <= cutoff,  # type: ignore[operator]
                    )
                )
                orders = list(result.scalars().all())
                for order in orders:
                    await cancel_order(db, order)
                    await create_notification(
                        db=db, user_id=order.buyer_id,
                        type=NotificationType.ORDER_CANCELLED,
                        title="Đơn hàng tự động hủy",
                        message=f"Đơn hàng #{str(order.id)[:8]} đã tự động hủy do quá {settings.ORDER_AUTO_CANCEL_HOURS}h chờ xử lý. Tiền đã được hoàn lại.",
                    )
                    await create_notification(
                        db=db, user_id=order.seller_id,
                        type=NotificationType.ORDER_CANCELLED,
                        title="Đơn hàng tự động hủy",
                        message=f"Đơn hàng #{str(order.id)[:8]} đã tự động hủy do quá hạn chờ xử lý.",
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
            logger.error("Auto-cancel worker error: %s", e)
        await asyncio.sleep(settings.ORDER_AUTO_CHECK_INTERVAL_SECONDS)


def start_auto_worker():
    global _worker_task, _cancel_worker_task
    if _worker_task is None:
        _worker_task = asyncio.create_task(auto_complete_worker())
        logger.info("Auto-complete worker started")
    if _cancel_worker_task is None:
        _cancel_worker_task = asyncio.create_task(auto_cancel_pending_worker())
        logger.info("Auto-cancel pending worker started")


def stop_auto_worker():
    global _worker_task, _cancel_worker_task
    if _worker_task:
        _worker_task.cancel()
        _worker_task = None
        logger.info("Auto-complete worker stopped")
    if _cancel_worker_task:
        _cancel_worker_task.cancel()
        _cancel_worker_task = None
        logger.info("Auto-cancel pending worker stopped")
