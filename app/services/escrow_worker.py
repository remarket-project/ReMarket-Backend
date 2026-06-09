"""Escrow auto-release background worker + return request auto-expire.

Khi GHN báo delivered → escrow.delivered_at được set.
Worker định kỳ kiểm tra: nếu escrow đã delivered quá ESCROW_DISPUTE_PERIOD_DAYS
mà không có dispute → auto release tiền cho seller.
Also auto-expires return requests if seller doesn't respond within 2 days.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.crud import crud_escrow, crud_wallet
from app.db.session import AsyncSessionLocal
from app.models.enums import EscrowStatus
from app.models.escrow import Escrow
from app.models.return_request import ReturnRequest, ReturnStatus

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None


async def _auto_release_worker() -> None:
    """Periodic worker: release escrows + auto-expire return requests."""
    interval = settings.ORDER_AUTO_CHECK_INTERVAL_SECONDS
    while True:
        try:
            async with AsyncSessionLocal() as db:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                # Auto-release escrows
                result = await db.execute(
                    select(Escrow).where(
                        Escrow.status == EscrowStatus.FUNDED.value,  # type: ignore[arg-type]
                        Escrow.delivered_at.is_not(None),  # type: ignore[arg-type]
                        Escrow.auto_release_at.is_not(None),  # type: ignore[arg-type]
                        Escrow.auto_release_at <= now,  # type: ignore[operator]
                    )
                )
                ready = list(result.scalars().all())
                for escrow in ready:
                    await _release_escrow(db, escrow)
                if ready:
                    logger.info("Auto-released %s escrow(s)", len(ready))

                # Auto-approve return requests (seller not responding in 2 days)
                expired_pending = await db.execute(
                    select(ReturnRequest).where(
                        ReturnRequest.status == ReturnStatus.PENDING.value,  # type: ignore[arg-type]
                        ReturnRequest.created_at < now - timedelta(days=2),  # type: ignore[operator]
                    )
                )
                for req in expired_pending.scalars():
                    req.status = ReturnStatus.SELLER_APPROVED.value
                    req.seller_responded_at = now.replace(tzinfo=None)
                    db.add(req)
                    logger.info("Auto-approved return %s (seller timeout)", req.id)

                # Auto-reject return requests (buyer not shipping in 7 days)
                expired_shipping = await db.execute(
                    select(ReturnRequest).where(
                        ReturnRequest.status == ReturnStatus.SELLER_APPROVED.value,  # type: ignore[arg-type]
                        ReturnRequest.seller_responded_at < now - timedelta(days=7),  # type: ignore[operator]
                    )
                )
                for req in expired_shipping.scalars():
                    req.status = ReturnStatus.SELLER_REJECTED.value
                    db.add(req)
                    logger.info("Auto-rejected return %s (buyer timeout)", req.id)

        except Exception:
            logger.exception("Escrow auto-release worker error")
        await asyncio.sleep(interval)


async def _release_escrow(db: AsyncSessionLocal, escrow: Escrow) -> None:  # type: ignore[arg-type]
    """Release a single escrow to seller."""
    try:
        await crud_wallet.transfer_locked_to_user(
            db=db,
            from_wallet_id=escrow.buyer_wallet_id,
            to_wallet_id=escrow.seller_wallet_id,
            amount=escrow.amount,
            order_id=escrow.order_id,
            description=f"Auto-release escrow {escrow.id}",
        )
        escrow.status = EscrowStatus.RELEASED.value
        escrow.released_at = datetime.now(timezone.utc)
        escrow.release_trigger = "auto"
        escrow.updated_at = datetime.now(timezone.utc)
        db.add(escrow)
        await db.commit()
    except Exception:
        logger.exception("Failed to release escrow %s", escrow.id)


def schedule_auto_release(escrow: Escrow) -> None:
    """Set auto_release_at after GHN confirms delivery.
    Called when escrow.delivered_at is set."""
    period = timedelta(hours=settings.ORDER_AUTO_COMPLETE_HOURS)
    escrow.auto_release_at = datetime.now(timezone.utc) + period
    escrow.release_trigger = "auto"


def start_worker() -> None:
    """Start the auto-release background worker (called from main.py lifespan)."""
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_auto_release_worker())
        logger.info("Escrow auto-release worker started")


def stop_worker() -> None:
    """Stop the auto-release background worker."""
    global _task
    if _task and not _task.done():
        _task.cancel()
        _task = None
        logger.info("Escrow auto-release worker stopped")
