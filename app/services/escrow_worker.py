"""Escrow auto-release background worker.

Khi GHN báo delivered → escrow.delivered_at được set.
Worker định kỳ kiểm tra: nếu escrow đã delivered quá ESCROW_DISPUTE_PERIOD_DAYS
mà không có dispute → auto release tiền cho seller.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.crud import crud_escrow, crud_wallet
from app.db.session import AsyncSessionLocal
from app.models.escrow import Escrow
from app.models.enums import EscrowStatus

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None


async def _auto_release_worker() -> None:
    """Periodic worker: release escrows that are past auto-release time."""
    interval = settings.ESCROW_AUTO_RELEASE_INTERVAL_SECONDS
    while True:
        try:
            async with AsyncSessionLocal() as db:
                now = datetime.now(timezone.utc)
                result = await db.execute(
                    select(Escrow).where(
                        Escrow.status == EscrowStatus.FUNDED.value,
                        Escrow.delivered_at.isnot(None),
                        Escrow.auto_release_at.isnot(None),
                        Escrow.auto_release_at <= now,
                    )
                )
                ready = list(result.scalars().all())
                for escrow in ready:
                    await _release_escrow(db, escrow)
                if ready:
                    logger.info("Auto-released %s escrow(s)", len(ready))
        except Exception:
            logger.exception("Escrow auto-release worker error")
        await asyncio.sleep(interval)


async def _release_escrow(db: AsyncSessionLocal, escrow: Escrow) -> None:
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
        await crud_escrow.update_escrow_status(
            db=db,
            escrow_id=escrow.id,
            new_status=EscrowStatus.RELEASED,
        )
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
    period = timedelta(days=settings.ESCROW_DISPUTE_PERIOD_DAYS)
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
