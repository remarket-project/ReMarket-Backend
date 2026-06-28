import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.websocket_manager import ws_manager
from app.crud.crud_notification import create_notification
from app.crud.crud_order_event import create_order_event
from app.crud.crud_user import get_admin_user_ids
from app.db.session import AsyncSessionLocal
from app.models.enums import NotificationType
from app.models.order import Order, OrderStatus

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None


async def delivery_simulation_worker():
    while True:
        try:
            notifications: list[dict] = []

            async with AsyncSessionLocal() as db:
                now = datetime.now(timezone.utc)

                # ─── 1. PENDING -> SHIPPING ──────────────────────────
                if settings.SIMULATION_PENDING_TO_SHIPPING_SECONDS > 0:
                    pending_result = await db.execute(
                        select(Order).where(
                            Order.status == OrderStatus.PENDING,  # type: ignore
                            Order.auto_ship_at.isnot(None),  # type: ignore
                            Order.auto_ship_at <= now,  # type: ignore
                        )
                    )
                    for order in pending_result.scalars().all():
                        order.status = OrderStatus.SHIPPING
                        order.updated_at = now
                        order.auto_deliver_at = now + timedelta(
                            seconds=settings.SIMULATION_SHIPPING_TO_DELIVERED_SECONDS
                        )
                        db.add(order)

                        await create_order_event(
                            db, order.id, "AUTO_SHIPPING",
                            "Tự động chuyển sang vận chuyển (simulation)",
                        )

                        notifications.append({
                            "buyer_id": order.buyer_id,
                            "seller_id": order.seller_id,
                            "order_id": order.id,
                        })

                        logger.info(
                            "Order %s auto-transition PENDING->SHIPPING",
                            str(order.id)[:8],
                        )

                # ─── 2. SHIPPING -> DELIVERED ────────────────────────
                if settings.SIMULATION_SHIPPING_TO_DELIVERED_SECONDS > 0:
                    shipping_result = await db.execute(
                        select(Order).where(
                            Order.status == OrderStatus.SHIPPING,  # type: ignore
                            Order.auto_deliver_at.isnot(None),  # type: ignore
                            Order.auto_deliver_at <= now,  # type: ignore
                        )
                    )
                    for order in shipping_result.scalars().all():
                        order.status = OrderStatus.DELIVERED
                        order.delivered_at = now
                        order.delivered_at_record = now
                        order.auto_complete_at = now + timedelta(
                            hours=settings.ORDER_AUTO_COMPLETE_HOURS
                        )
                        order.updated_at = now
                        db.add(order)

                        await create_order_event(
                            db, order.id, "AUTO_DELIVERED",
                            "Tự động chuyển sang đã giao (simulation)",
                        )

                        await create_notification(
                            db=db, user_id=order.buyer_id,
                            type=NotificationType.ORDER_DELIVERED,
                            title="Hàng đã được giao",
                            message=f"Đơn hàng #{str(order.id)[:8]} đã được giao thành công.",
                            data={"order_id": str(order.id)},
                        )

                        notifications.append({
                            "buyer_id": order.buyer_id,
                            "seller_id": order.seller_id,
                            "order_id": order.id,
                        })

                        logger.info(
                            "Order %s auto-transition SHIPPING->DELIVERED",
                            str(order.id)[:8],
                        )

                await db.commit()

            # ─── WS Broadcast (sau khi session da close) ──────────
            if notifications:
                admin_ids = []
                try:
                    async with AsyncSessionLocal() as admin_db:
                        admin_ids = await get_admin_user_ids(admin_db)
                except Exception:
                    pass

                for n in notifications:
                    try:
                        await ws_manager.send_to_user(n["buyer_id"], {
                            "type": "order_status_updated",
                            "order_id": str(n["order_id"]),
                        })
                        await ws_manager.send_to_user(n["seller_id"], {
                            "type": "order_status_updated",
                            "order_id": str(n["order_id"]),
                        })
                        if admin_ids:
                            await ws_manager.broadcast_to_users(admin_ids, {
                                "type": "order_status_updated",
                                "order_id": str(n["order_id"]),
                            })
                    except Exception as e:
                        logger.warning(
                            "WS broadcast failed for order %s: %s",
                            str(n["order_id"])[:8], e,
                        )

        except Exception as e:
            logger.error("Delivery simulation worker error: %s", e)

        await asyncio.sleep(settings.SIMULATION_CHECK_INTERVAL_SECONDS)


def start_delivery_simulation_worker():
    global _worker_task
    if _worker_task is None:
        _worker_task = asyncio.create_task(delivery_simulation_worker())
        logger.info("Delivery simulation worker started")


def stop_delivery_simulation_worker():
    global _worker_task
    if _worker_task:
        _worker_task.cancel()
        _worker_task = None
        logger.info("Delivery simulation worker stopped")
