from typing import List
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import CurrentUser, SessionDep
from app.models.user import User
from app.models.listing import Listing
from app.models.order import Order
from app.models.enums import OfferStatus, ListingStatus, OrderStatus, NotificationType
from app.schemas.offer import OfferCreate, OfferRead, OfferStatusUpdate
from app.crud import crud_notification, crud_offer, crud_escrow, crud_wallet

router = APIRouter(prefix="/offers", tags=["Offers"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/", response_model=OfferRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/hour")
async def create_offer(
    current_user: CurrentUser,
    db: SessionDep,
    request: Request,
    offer_in: OfferCreate,
):
    """Tạo yêu cầu mua (offer) cho bài đăng"""
    try:
        offer = await crud_offer.create_offer(
            db,
            listing_id=offer_in.listing_id,
            buyer_id=current_user.id,
            offer_price=offer_in.offer_price
        )

        result = await db.execute(select(Listing).where(Listing.id == offer.listing_id))
        listing = result.scalar_one_or_none()
        if listing:
            await crud_notification.create_notification(
                db=db,
                user_id=listing.seller_id,
                type=NotificationType.OFFER_RECEIVED,
                title="Nhận yêu cầu mua mới",
                message=f"Bạn nhận được một yêu cầu mua cho '{listing.title}'.",
                data={"offer_id": str(offer.id),
                      "listing_id": str(listing.id)},
            )
        return offer
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me/sent", response_model=List[OfferRead])
async def get_my_sent_offers(
    current_user: CurrentUser,
    db: SessionDep,
    skip: int = 0,
    limit: int = 10,
):
    """Danh sách yêu cầu mua tôi đã gửi"""
    offers = await crud_offer.get_user_sent_offers(db, current_user.id, skip, limit)
    return offers


@router.get("/me/received", response_model=List[OfferRead])
async def get_my_received_offers(
    current_user: CurrentUser,
    db: SessionDep,
    skip: int = 0,
    limit: int = 10,
):
    """Danh sách yêu cầu mua tôi nhận được"""
    offers = await crud_offer.get_seller_received_offers(db, current_user.id, skip, limit)
    return offers


@router.get("/listing/{listing_id}", response_model=List[OfferRead])
async def get_offers_for_listing(
    current_user: CurrentUser,
    db: SessionDep,
    listing_id: uuid.UUID,
    skip: int = 0,
    limit: int = 10,
):
    """Danh sách yêu cầu mua cho một bài đăng"""
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Bài đăng không tìm thấy")

    if listing.seller_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xem yêu cầu mua cho bài đăng này"
        )

    offers = await crud_offer.get_offers_by_listing(db, listing_id, skip, limit)
    return offers


@router.patch("/{offer_id}/status", response_model=OfferRead)
async def update_offer_status(
    current_user: CurrentUser,
    db: SessionDep,
    offer_id: uuid.UUID,
    status_update: OfferStatusUpdate,
):
    """Cập nhật trạng thái yêu cầu mua"""
    offer = await crud_offer.get_offer_by_id(db, offer_id)
    if not offer:
        raise HTTPException(
            status_code=404, detail="Yêu cầu mua không tìm thấy")

    result = await db.execute(select(Listing).where(Listing.id == offer.listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Bài đăng không tìm thấy")

    is_seller = listing.seller_id == current_user.id
    is_buyer = offer.buyer_id == current_user.id

    if not is_seller and not is_buyer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền cập nhật yêu cầu mua này"
        )

    if offer.status in {OfferStatus.ACCEPTED, OfferStatus.REJECTED, OfferStatus.EXPIRED}:
        raise HTTPException(
            status_code=400,
            detail=f"Không thể thay đổi yêu cầu ở trạng thái: {offer.status}"
        )

    if is_seller and offer.status != OfferStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Người bán chỉ có thể cập nhật yêu cầu PENDING. Trạng thái hiện tại: {offer.status}"
        )

    if is_seller and status_update.status not in {
        OfferStatus.ACCEPTED,
        OfferStatus.REJECTED,
        OfferStatus.COUNTERED,
    }:
        raise HTTPException(
            status_code=400, detail="Người bán chỉ có thể đặt ACCEPTED/REJECTED/COUNTERED")

    if is_seller and status_update.status == OfferStatus.COUNTERED and status_update.offer_price is None:
        raise HTTPException(
            status_code=400, detail="Trạng thái COUNTERED cần có offer_price")

    if is_buyer:
        if offer.status == OfferStatus.PENDING:
            if status_update.status != OfferStatus.REJECTED:
                raise HTTPException(
                    status_code=400,
                    detail="Người mua chỉ có thể hủy yêu cầu PENDING"
                )
        elif offer.status == OfferStatus.COUNTERED:
            if status_update.status not in {OfferStatus.ACCEPTED, OfferStatus.REJECTED}:
                raise HTTPException(
                    status_code=400,
                    detail="Người mua chỉ có thể chấp nhận hoặc từ chối yêu cầu COUNTERED"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Người mua không thể cập nhật yêu cầu với trạng thái: {offer.status}"
            )

    if status_update.status == OfferStatus.ACCEPTED and listing.status == ListingStatus.SOLD:
        raise HTTPException(status_code=400, detail="Bài đăng đã bán")

    previous_status = offer.status
    try:
        updated_offer, rejected_offers = await crud_offer.update_offer_status(
            db,
            offer_id,
            status_update.status,
            counter_price=status_update.offer_price,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if status_update.status == OfferStatus.ACCEPTED:
        order = Order(
            buyer_id=offer.buyer_id,
            seller_id=listing.seller_id,
            listing_id=offer.listing_id,
            final_price=offer.offer_price,
            status=OrderStatus.PENDING
        )
        db.add(order)

        listing.status = ListingStatus.SOLD
        db.add(listing)

        # Auto-create escrow for newly created order if missing.
        await db.flush()
        existing_escrow = await crud_escrow.get_escrow_by_order_id(db, order.id)
        if not existing_escrow:
            buyer_wallet = await crud_wallet.get_or_create_wallet(db, offer.buyer_id)
            seller_wallet = await crud_wallet.get_or_create_wallet(db, listing.seller_id)
            await crud_escrow.create_escrow(
                db=db,
                order_id=order.id,
                amount=offer.offer_price,
                buyer_wallet_id=buyer_wallet.id,
                seller_wallet_id=seller_wallet.id,
            )

    await db.commit()
    await db.refresh(updated_offer)

    if rejected_offers:
        for rejected_offer in rejected_offers:
            await crud_notification.create_notification(
                db=db,
                user_id=rejected_offer.buyer_id,
                type=NotificationType.OFFER_REJECTED,
                title="Yêu cầu mua bị từ chối",
                message=f"Yêu cầu mua cho '{listing.title}' đã bị từ chối do yêu cầu khác được chấp nhận.",
                data={"offer_id": str(rejected_offer.id),
                      "listing_id": str(listing.id)},
            )

    if status_update.status == OfferStatus.ACCEPTED:
        await crud_notification.create_notification(
            db=db,
            user_id=offer.buyer_id,
            type=NotificationType.ORDER_CREATED,
            title="Đơn hàng đã tạo",
            message=f"Yêu cầu mua cho '{listing.title}' đã được chấp nhận. Đơn hàng đã tạo.",
            data={"listing_id": str(listing.id)},
        )
        await crud_notification.create_notification(
            db=db,
            user_id=listing.seller_id,
            type=NotificationType.ORDER_CREATED,
            title="Đơn hàng đã tạo",
            message=f"Bạn đã chấp nhận yêu cầu mua cho '{listing.title}'. Đơn hàng đã tạo.",
            data={"listing_id": str(listing.id)},
        )

    if status_update.status in {OfferStatus.ACCEPTED, OfferStatus.REJECTED, OfferStatus.COUNTERED}:
        notification_type = {
            OfferStatus.ACCEPTED: NotificationType.OFFER_ACCEPTED,
            OfferStatus.REJECTED: NotificationType.OFFER_REJECTED,
            OfferStatus.COUNTERED: NotificationType.OFFER_COUNTERED,
        }[status_update.status]

        if is_seller:
            target_user_id = offer.buyer_id
            message = f"Yêu cầu mua cho '{listing.title}' đã được cập nhật thành '{status_update.status}'."
        else:
            target_user_id = listing.seller_id
            message = f"Người mua đã trả lời yêu cầu mua ngược lại cho '{listing.title}' với '{status_update.status}'."

        await crud_notification.create_notification(
            db=db,
            user_id=target_user_id,
            type=notification_type,
            title="Trạng thái yêu cầu mua được cập nhật",
            message=message,
            data={"offer_id": str(offer.id), "listing_id": str(listing.id)},
        )

    if previous_status != OfferStatus.EXPIRED and updated_offer.status == OfferStatus.EXPIRED:
        await crud_notification.create_notification(
            db=db,
            user_id=offer.buyer_id,
            type=NotificationType.OFFER_EXPIRED,
            title="Yêu cầu mua hết hạn",
            message="Yêu cầu mua của bạn đã hết hạn do quá thời gian.",
            data={"offer_id": str(offer.id), "listing_id": str(listing.id)},
        )

    return updated_offer


@router.get("/{offer_id}", response_model=OfferRead)
async def get_offer(
    current_user: CurrentUser,
    db: SessionDep,
    offer_id: uuid.UUID,
):
    """Lấy chi tiết một yêu cầu mua"""
    offer = await crud_offer.get_offer_by_id(db, offer_id)
    if not offer:
        raise HTTPException(
            status_code=404, detail="Yêu cầu mua không tìm thấy")

    result = await db.execute(select(Listing).where(Listing.id == offer.listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Bài đăng không tìm thấy")

    if current_user.id != offer.buyer_id and current_user.id != listing.seller_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xem yêu cầu mua này"
        )

    return offer
