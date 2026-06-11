"""
CRUD operations for Offer model.

Handles creation, retrieval, and updates of offers (negotiations).
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, desc, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.models.enums import EscrowStatus, ListingStatus, OfferStatus, OrderStatus, PaymentMethod
from app.models.listing import Listing
from app.models.offer import Offer
from app.models.order import Order
from app.schemas.order import ShippingAddressInput


def utc_now() -> datetime:
    """Return UTC datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def expire_stale_offers(db: AsyncSession) -> int:
    """Expire stale offers: PENDING/COUNTERED > 48h, ACCEPTED > 24h (confirm timeout)."""
    now = utc_now()
    cutoff_pending = now - timedelta(hours=settings.OFFER_EXPIRE_HOURS)
    cutoff_accepted = now - timedelta(hours=settings.OFFER_CONFIRM_HOURS)

    # Expire PENDING/COUNTERED quá 48h
    result_pending = await db.execute(
        update(Offer)
        .where(
            and_(
                Offer.created_at <= cutoff_pending,  # type: ignore[arg-type]
                Offer.status.in_([OfferStatus.PENDING, OfferStatus.COUNTERED]),  # type: ignore[attr-defined]
            )
        )
        .values(status=OfferStatus.EXPIRED, updated_at=now)
    )

    # Expire ACCEPTED quá 24h + revert listing về ACTIVE
    result_accepted = await db.execute(
        select(Offer).where(
            and_(
                Offer.created_at <= cutoff_accepted,  # type: ignore[arg-type]
                Offer.status == OfferStatus.ACCEPTED,
            )
        )
    )
    expired_accepted_offers = list(result_accepted.scalars().all())

    for expired_offer in expired_accepted_offers:
        expired_offer.status = OfferStatus.EXPIRED
        expired_offer.updated_at = now
        db.add(expired_offer)

        # Revert listing về ACTIVE
        listing_result = await db.execute(
            select(Listing).where(Listing.id == expired_offer.listing_id).with_for_update()  # type: ignore[arg-type]
        )
        listing = listing_result.scalar_one_or_none()
        if listing and listing.status == ListingStatus.RESERVED:
            listing.status = ListingStatus.ACTIVE
            db.add(listing)

    await db.commit()
    return (result_pending.rowcount or 0) + len(expired_accepted_offers)


async def create_offer(
    db: AsyncSession,
    listing_id: uuid.UUID,
    buyer_id: uuid.UUID,
    offer_price
) -> Offer:
    """Create offer with validation — FIXED race condition with FOR UPDATE."""
    await expire_stale_offers(db)

    # Lock listing row to prevent concurrent status change
    result = await db.execute(
        select(Listing).where(Listing.id == listing_id).with_for_update()  # type: ignore[arg-type]
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise ValueError("Listing not found")

    if listing.seller_id == buyer_id:
        raise ValueError("You cannot make an offer on your own listing")

    if not listing.is_negotiable:
        raise ValueError("This listing is not negotiable")

    if offer_price <= 0:
        raise ValueError("Giá đề nghị phải lớn hơn 0")

    if listing.status != ListingStatus.ACTIVE:
        raise ValueError(f"Cannot make offer on listing with status: {listing.status}")

    if not listing.is_negotiable:
        raise ValueError("This listing is not negotiable")

    # Lock-check for existing pending offer (same transaction)
    pending_result = await db.execute(
        select(Offer).where(
            and_(
                Offer.buyer_id == buyer_id,  # type: ignore[arg-type]
                Offer.listing_id == listing_id,  # type: ignore[arg-type]
                or_(Offer.status == OfferStatus.PENDING, Offer.status == OfferStatus.COUNTERED)  # type: ignore[arg-type]
            )
        ).with_for_update()
    )
    if pending_result.scalar_one_or_none():
        raise ValueError("You already have a pending offer on this listing")

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
    result = await db.execute(select(Offer).where(Offer.id == offer_id))  # type: ignore[arg-type]
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
        .where(Offer.buyer_id == buyer_id)  # type: ignore[arg-type]
        .order_by(desc(Offer.created_at))  # type: ignore[arg-type]
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
        .where(Listing.seller_id == seller_id)  # type: ignore[arg-type]
        .order_by(desc(Offer.created_at))  # type: ignore[arg-type]
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
        .where(Offer.listing_id == listing_id)  # type: ignore[arg-type]
        .order_by(desc(Offer.created_at))  # type: ignore[arg-type]
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
    """Update offer status — FIXED race condition with FOR UPDATE on offer + listing."""
    # Lock offer row
    result = await db.execute(
        select(Offer).where(Offer.id == offer_id).with_for_update()  # type: ignore[arg-type]
    )
    offer = result.scalar_one_or_none()
    if not offer:
        raise ValueError("Offer not found")

    rejected_offers: list[Offer] = []

    if new_status == OfferStatus.COUNTERED:
        if counter_price is None:
            raise ValueError("Countered offer requires counter price")
        offer.offer_price = counter_price
        offer.created_at = utc_now()  # Reset timer để buyer có 48h từ lúc counter

    offer.status = new_status
    offer.updated_at = utc_now()

    # If buyer rejects an ACCEPTED offer, revert listing to ACTIVE
    if offer.status == OfferStatus.REJECTED:
        listing_result = await db.execute(
            select(Listing).where(Listing.id == offer.listing_id).with_for_update()  # type: ignore[arg-type]
        )
        listing = listing_result.scalar_one_or_none()
        if listing and listing.status == ListingStatus.RESERVED:
            listing.status = ListingStatus.ACTIVE
            db.add(listing)

    # If accepting, lock listing + reject other offers atomically
    if new_status == OfferStatus.ACCEPTED:
        # Lock listing to prevent double-sell
        listing_result = await db.execute(
            select(Listing).where(Listing.id == offer.listing_id).with_for_update()  # type: ignore[arg-type]
        )
        listing = listing_result.scalar_one_or_none()
        if not listing:
            raise ValueError("Listing not found")
        if listing.status == ListingStatus.SOLD:
            raise ValueError("This listing has already been sold")
        if listing.status == ListingStatus.RESERVED:
            raise ValueError("Listing is currently reserved for another buyer")

        # Lock and reject other pending/countered offers
        reject_result = await db.execute(
            select(Offer)
            .where(
                and_(
                    Offer.listing_id == offer.listing_id,  # type: ignore[arg-type]
                    Offer.id != offer.id,  # type: ignore[arg-type]
                    Offer.status.in_([OfferStatus.PENDING, OfferStatus.COUNTERED]),  # type: ignore[attr-defined]
                )
            )
            .with_for_update(nowait=False)
        )
        rejected_offers = list(reject_result.scalars().all())
        for rejected_offer in rejected_offers:
            rejected_offer.status = OfferStatus.REJECTED
            rejected_offer.updated_at = utc_now()

        listing.status = ListingStatus.RESERVED
        db.add(listing)

    db.add(offer)
    await db.commit()
    await db.refresh(offer)
    return offer, rejected_offers


async def confirm_offer_and_create_order(
    db: AsyncSession,
    offer_id: uuid.UUID,
    buyer_id: uuid.UUID,
    shipping_address: ShippingAddressInput | None = None,
    payment_method: PaymentMethod = PaymentMethod.WALLET,
) -> Order:
    """Buyer xác nhận đặt hàng sau khi seller đồng ý offer.

    Tạo Order + Escrow + Fund trong 1 transaction.
    """
    from app.crud import crud_escrow, crud_wallet

    # Lock offer
    result = await db.execute(
        select(Offer).where(Offer.id == offer_id).with_for_update()  # type: ignore[arg-type]
    )
    offer = result.scalar_one_or_none()
    if not offer:
        raise ValueError("Offer not found")
    if offer.status != OfferStatus.ACCEPTED:
        raise ValueError(f"Cannot confirm offer with status: {offer.status}")
    if offer.buyer_id != buyer_id:
        raise ValueError("Only the buyer can confirm this offer")

    # Check 24h expiry
    cutoff = utc_now() - timedelta(hours=settings.OFFER_CONFIRM_HOURS)
    if offer.created_at <= cutoff:
        # Expire the offer and revert listing
        offer.status = OfferStatus.EXPIRED
        offer.updated_at = utc_now()
        db.add(offer)
        listing_revert = await db.execute(
            select(Listing).where(Listing.id == offer.listing_id).with_for_update()  # type: ignore[arg-type]
        )
        listing_r = listing_revert.scalar_one_or_none()
        if listing_r and listing_r.status == ListingStatus.RESERVED:
            listing_r.status = ListingStatus.ACTIVE
            db.add(listing_r)
        await db.commit()
        raise ValueError("Offer has expired (over 24 hours)")

    # Lock listing
    listing_result = await db.execute(
        select(Listing).where(Listing.id == offer.listing_id).with_for_update()  # type: ignore[arg-type]
    )
    listing = listing_result.scalar_one_or_none()
    if not listing:
        raise ValueError("Listing not found")
    if listing.status != ListingStatus.RESERVED:
        raise ValueError(f"Listing is not reserved: {listing.status}")

    # Create Order
    order = Order(
        buyer_id=offer.buyer_id,
        seller_id=listing.seller_id,
        listing_id=offer.listing_id,
        final_price=offer.offer_price,
        status=OrderStatus.PENDING,
        payment_method=payment_method,
        offer_id=offer.id,
    )
    db.add(order)
    await db.flush()

    # Save shipping address if provided
    if shipping_address:
        order.shipping_name = shipping_address.name
        order.shipping_phone = shipping_address.phone
        order.shipping_province = shipping_address.province
        order.shipping_district = shipping_address.district
        order.shipping_ward = shipping_address.ward
        order.shipping_address_detail = shipping_address.address_detail
        order.shipping_note = shipping_address.note
        order.shipping_province_id = shipping_address.province_id
        order.shipping_district_id = shipping_address.district_id
        order.shipping_ward_code = shipping_address.ward_code

    # Create Escrow
    buyer_wallet = await crud_wallet.get_or_create_wallet(db, offer.buyer_id)
    seller_wallet = await crud_wallet.get_or_create_wallet(db, listing.seller_id)

    escrow = await crud_escrow.create_escrow(
        db=db,
        order_id=order.id,
        amount=offer.offer_price,
        buyer_wallet_id=buyer_wallet.id,
        seller_wallet_id=seller_wallet.id,
    )

    # Fund escrow from buyer wallet (only for wallet payment)
    if payment_method == PaymentMethod.WALLET:
        await crud_wallet.lock_balance(
            db=db,
            wallet_id=buyer_wallet.id,
            amount=offer.offer_price,
            order_id=order.id,
            description=f"Thanh toán đơn hàng #{order.id} từ offer",
        )
        escrow.status = EscrowStatus.FUNDED.value
        escrow.funded_at = utc_now()
        escrow.updated_at = utc_now()
        db.add(escrow)

    # Set listing SOLD
    listing.status = ListingStatus.SOLD
    db.add(listing)

    # Link order_id to offer
    offer.status = OfferStatus.CONFIRMED
    offer.order_id = order.id
    offer.updated_at = utc_now()
    db.add(offer)

    await db.commit()
    await db.refresh(order)
    return order
