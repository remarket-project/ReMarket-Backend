"""
CRUD operations for Offer model.

Handles creation, retrieval, and updates of offers (negotiations).
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.models.enums import ListingStatus, OfferStatus
from app.models.listing import Listing
from app.models.offer import Offer


def utc_now() -> datetime:
    """Return UTC datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def expire_stale_offers(db: AsyncSession) -> int:
    """Expire PENDING/COUNTERED offers older than configured TTL."""
    cutoff = utc_now() - timedelta(hours=settings.OFFER_EXPIRE_HOURS)
    result = await db.execute(
        update(Offer)
        .where(
            and_(
                Offer.created_at <= cutoff,
                Offer.status.in_([OfferStatus.PENDING, OfferStatus.COUNTERED]),
            )
        )
        .values(status=OfferStatus.EXPIRED, updated_at=utc_now())
    )
    await db.commit()
    return int(result.rowcount or 0)


async def check_existing_pending_offer(
    db: AsyncSession, buyer_id: uuid.UUID, listing_id: uuid.UUID
) -> bool:
    """Check if buyer already has pending/countered offer on listing."""
    result = await db.execute(
        select(Offer).where(
            and_(
                Offer.buyer_id == buyer_id,
                Offer.listing_id == listing_id,
                or_(
                    Offer.status == OfferStatus.PENDING,
                    Offer.status == OfferStatus.COUNTERED
                )
            )
        )
    )
    return result.scalar_one_or_none() is not None


async def create_offer(
    db: AsyncSession,
    listing_id: uuid.UUID,
    buyer_id: uuid.UUID,
    offer_price
) -> Offer:
    """Create offer with validation."""
    await expire_stale_offers(db)

    # Check listing exists
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise ValueError("Listing not found")

    # Buyer can't offer on own listing
    if listing.seller_id == buyer_id:
        raise ValueError("You cannot make an offer on your own listing")

    # Listing must be ACTIVE
    if listing.status != ListingStatus.ACTIVE:
        raise ValueError(
            f"Cannot make offer on listing with status: {listing.status}")

    # Listing must be negotiable
    if not listing.is_negotiable:
        raise ValueError("This listing is not negotiable")

    # Anti-spam: one active offer per listing per buyer
    if await check_existing_pending_offer(db, buyer_id, listing_id):
        raise ValueError("You already have a pending offer on this listing")

    # Create offer
    db_obj = Offer(
        listing_id=listing_id,
        buyer_id=buyer_id,
        offer_price=offer_price,
        status=OfferStatus.PENDING
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def get_offer_by_id(db: AsyncSession, offer_id: uuid.UUID) -> Offer | None:
    """Get offer by ID."""
    await expire_stale_offers(db)
    result = await db.execute(select(Offer).where(Offer.id == offer_id))
    return result.scalar_one_or_none()


async def get_user_sent_offers(
    db: AsyncSession,
    buyer_id: uuid.UUID,
    skip: int = 0,
    limit: int = 10
) -> list[Offer]:
    """Get offers sent by buyer."""
    await expire_stale_offers(db)
    result = await db.execute(
        select(Offer)
        .where(Offer.buyer_id == buyer_id)
        .order_by(Offer.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_seller_received_offers(
    db: AsyncSession,
    seller_id: uuid.UUID,
    skip: int = 0,
    limit: int = 10
) -> list[Offer]:
    """Get offers received by seller on all their listings."""
    await expire_stale_offers(db)
    result = await db.execute(
        select(Offer)
        .join(Listing)
        .where(Listing.seller_id == seller_id)
        .order_by(Offer.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_offers_by_listing(
    db: AsyncSession,
    listing_id: uuid.UUID,
    skip: int = 0,
    limit: int = 10
) -> list[Offer]:
    """Get all offers for a listing."""
    await expire_stale_offers(db)
    result = await db.execute(
        select(Offer)
        .where(Offer.listing_id == listing_id)
        .order_by(Offer.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_offer_status(
    db: AsyncSession,
    offer_id: uuid.UUID,
    new_status: OfferStatus,
    counter_price=None,
) -> tuple[Offer, list[Offer]]:
    """Update offer status."""
    result = await db.execute(select(Offer).where(Offer.id == offer_id))
    offer = result.scalar_one_or_none()

    if not offer:
        raise ValueError("Offer not found")

    rejected_offers: list[Offer] = []

    if new_status == OfferStatus.COUNTERED:
        if counter_price is None:
            raise ValueError("Countered offer requires counter price")
        offer.offer_price = counter_price

    offer.status = new_status
    offer.updated_at = utc_now()

    # If accepting, reject other pending offers on same listing
    if new_status == OfferStatus.ACCEPTED:
        reject_result = await db.execute(
            select(Offer)
            .where(
                and_(
                    Offer.listing_id == offer.listing_id,
                    Offer.id != offer.id,
                    Offer.status.in_([
                        OfferStatus.PENDING,
                        OfferStatus.COUNTERED,
                    ]),
                )
            )
            .with_for_update(nowait=False)
        )
        rejected_offers = list(reject_result.scalars().all())
        for rejected_offer in rejected_offers:
            rejected_offer.status = OfferStatus.REJECTED
            rejected_offer.updated_at = utc_now()

        # Mark listing as sold
        await db.execute(
            update(Listing)
            .where(Listing.id == offer.listing_id)
            .values(status=ListingStatus.SOLD)
        )

    db.add(offer)
    await db.commit()
    await db.refresh(offer)
    return offer, rejected_offers
