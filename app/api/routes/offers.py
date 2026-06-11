import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.future import select

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.websocket_manager import ws_manager
from app.crud import crud_notification, crud_offer
from app.models.enums import NotificationType, OfferStatus
from app.models.listing import Listing
from app.schemas.offer import (
    OfferConfirmRequest,
    OfferCreate,
    OfferRead,
    OfferStatusUpdate,
)
from app.schemas.order import OrderRead

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

        where_cond: Any = Listing.id == offer.listing_id  # type: ignore[arg-type]
        result = await db.execute(select(Listing).where(where_cond))
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
            await ws_manager.send_to_user(listing.seller_id, {
                "type": "offer_received",
                "user_id": str(listing.seller_id),
            })

            # Auto-create chat conversation and post notification message
            try:
                from app.crud import crud_chat
                existing_chat = await crud_chat.get_conversation_by_listing_and_user(
                    db, offer.listing_id, current_user.id
                )
                if not existing_chat:
                    existing_chat = await crud_chat.create_conversation(
                        db, listing_id=offer.listing_id
                    )
                    await crud_chat.add_participant(db, existing_chat.id, current_user.id)
                    await crud_chat.add_participant(db, existing_chat.id, listing.seller_id)

                formatted_price = f"{offer.offer_price:,.0f} VND"
                message = await crud_chat.post_message(
                    db,
                    conversation_id=existing_chat.id,
                    sender_id=current_user.id,
                    content=f"Mình đã gửi đề nghị {formatted_price} cho bạn.",
                )
                await ws_manager.send_to_user(listing.seller_id, {
                    "type": "chat_message",
                    "conversation_id": str(existing_chat.id),
                    "message": {
                        "id": str(message.id),
                        "conversation_id": str(message.conversation_id),
                        "sender_id": str(message.sender_id),
                        "content": message.content,
                        "created_at": message.created_at.isoformat(),
                    },
                })
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Failed to auto-create conversation: %s", e)
        return offer
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/me/sent", response_model=list[OfferRead])
async def get_my_sent_offers(
    current_user: CurrentUser,
    db: SessionDep,
    skip: int = 0,
    limit: int = 10,
):
    """Danh sách yêu cầu mua tôi đã gửi"""
    offers = await crud_offer.get_user_sent_offers(db, current_user.id, skip, limit)
    return offers


@router.get("/me/received", response_model=list[OfferRead])
async def get_my_received_offers(
    current_user: CurrentUser,
    db: SessionDep,
    skip: int = 0,
    limit: int = 10,
):
    """Danh sách yêu cầu mua tôi nhận được"""
    offers = await crud_offer.get_seller_received_offers(db, current_user.id, skip, limit)
    return offers


@router.get("/listing/{listing_id}", response_model=list[OfferRead])
async def get_offers_for_listing(
    current_user: CurrentUser,
    db: SessionDep,
    listing_id: uuid.UUID,
    skip: int = 0,
    limit: int = 10,
):
    """Danh sách yêu cầu mua cho một bài đăng"""
    where_cond: Any = Listing.id == listing_id  # type: ignore[arg-type]
    result = await db.execute(select(Listing).where(where_cond))
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


@router.post("/{offer_id}/confirm", response_model=OrderRead)
async def confirm_offer_order(
    current_user: CurrentUser,
    db: SessionDep,
    offer_id: uuid.UUID,
    confirm_in: OfferConfirmRequest,
):
    """Buyer xác nhận đặt hàng sau khi seller đồng ý offer. Tạo Order + Escrow + Fund."""
    offer = await crud_offer.get_offer_by_id(db, offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer không tìm thấy")
    if offer.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Chỉ người mua mới có thể xác nhận")

    try:
        order = await crud_offer.confirm_offer_and_create_order(
            db, offer_id, current_user.id,
            shipping_address=confirm_in.shipping_address,
            payment_method=confirm_in.payment_method,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Notifications
    listing_result = await db.execute(
        select(Listing).where(Listing.id == offer.listing_id)
    )
    listing = listing_result.scalar_one_or_none()
    listing_title = listing.title if listing else ""

    await crud_notification.create_notification(
        db=db,
        user_id=order.seller_id,
        type=NotificationType.ORDER_CREATED,
        title="Đơn hàng mới",
        message=f"Người mua đã xác nhận đặt hàng cho '{listing_title}'.",
        data={"order_id": str(order.id), "listing_id": str(order.listing_id)},
    )

    await ws_manager.send_to_user(order.seller_id, {
        "type": "new_order",
        "order_id": str(order.id),
    })

    # WS: notify admins about new order
    from app.crud.crud_user import get_admin_user_ids
    admin_ids = await get_admin_user_ids(db)
    if admin_ids:
        await ws_manager.broadcast_to_users(admin_ids, {
            "type": "new_order",
            "order_id": str(order.id),
        })

    await ws_manager.broadcast_to_all({
        "type": "listing_sold_broadcast",
        "listing_id": str(order.listing_id),
    })

    return order


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

    where_cond: Any = Listing.id == offer.listing_id  # type: ignore[arg-type]
    result = await db.execute(select(Listing).where(where_cond))
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

    # ACCEPTED no longer terminal — buyer can reject
    if offer.status in {OfferStatus.REJECTED, OfferStatus.EXPIRED}:
        raise HTTPException(
            status_code=400,
            detail=f"Không thể thay đổi yêu cầu ở trạng thái: {offer.status}"
        )

    if is_seller and offer.status not in {OfferStatus.PENDING, OfferStatus.COUNTERED}:
        raise HTTPException(
            status_code=400,
            detail=f"Người bán chỉ có thể cập nhật yêu cầu PENDING hoặc COUNTERED. Trạng thái hiện tại: {offer.status}"
        )

    if is_seller and offer.status == OfferStatus.COUNTERED and offer.last_action_by == listing.seller_id:
        raise HTTPException(
            status_code=400,
            detail="Bạn đã phản hồi đề nghị này. Đang chờ người mua trả lời."
        )

    if is_seller and status_update.status not in {
        OfferStatus.ACCEPTED,
        OfferStatus.REJECTED,
        OfferStatus.COUNTERED,
    }:
        raise HTTPException(
            status_code=400, detail="Người bán chỉ có thể đặt ACCEPTED/REJECTED/COUNTERED")

    if is_buyer:
        if offer.status == OfferStatus.PENDING:
            if status_update.status != OfferStatus.REJECTED:
                raise HTTPException(
                    status_code=400,
                    detail="Người mua chỉ có thể hủy yêu cầu PENDING"
                )
        elif offer.status == OfferStatus.COUNTERED:
            if status_update.status not in {OfferStatus.ACCEPTED, OfferStatus.REJECTED, OfferStatus.COUNTERED}:
                raise HTTPException(
                    status_code=400,
                    detail="Người mua chỉ có thể chấp nhận, từ chối hoặc phản đề nghị yêu cầu COUNTERED"
                )
            if status_update.status == OfferStatus.COUNTERED and offer.last_action_by == offer.buyer_id:
                raise HTTPException(
                    status_code=400,
                    detail="Bạn đã phản hồi đề nghị này. Đang chờ người bán trả lời."
                )
        elif offer.status == OfferStatus.ACCEPTED:
            if status_update.status != OfferStatus.REJECTED:
                raise HTTPException(
                    status_code=400,
                    detail="Người mua chỉ có thể từ chối yêu cầu đã được đồng ý"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Người mua không thể cập nhật yêu cầu với trạng thái: {offer.status}"
            )

    if status_update.status == OfferStatus.COUNTERED and status_update.offer_price is None:
        raise HTTPException(
            status_code=400, detail="Trạng thái COUNTERED cần có offer_price")

    # Remove redundant check — CRUD handles listing.status validation with FOR UPDATE
    try:
        updated_offer, rejected_offers = await crud_offer.update_offer_status(
            db,
            offer_id,
            status_update.status,
            counter_price=status_update.offer_price,
            acting_user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

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
            await ws_manager.send_to_user(rejected_offer.buyer_id, {
                "type": "offer_rejected",
                "offer_id": str(rejected_offer.id),
                "listing_id": str(listing.id),
            })

    if status_update.status == OfferStatus.ACCEPTED:
        await crud_notification.create_notification(
            db=db,
            user_id=offer.buyer_id,
            type=NotificationType.OFFER_ACCEPTED,
            title="Người bán đã đồng ý",
            message=(
                f"Người bán đã đồng ý với đề nghị của bạn cho '{listing.title}'. "
                f"Bạn có {settings.OFFER_CONFIRM_HOURS}h để xác nhận đặt hàng."
            ),
            data={"offer_id": str(offer.id), "listing_id": str(listing.id)},
        )
        await ws_manager.send_to_user(offer.buyer_id, {
            "type": "offer_accepted",
            "offer_id": str(offer.id),
            "listing_id": str(listing.id),
            "expires_in_hours": settings.OFFER_CONFIRM_HOURS,
        })

        await crud_notification.create_notification(
            db=db,
            user_id=listing.seller_id,
            type=NotificationType.OFFER_ACCEPTED,
            title="Đã đồng ý với đề nghị",
            message=f"Bạn đã đồng ý với đề nghị mua '{listing.title}'. Đang chờ người mua xác nhận.",
            data={"offer_id": str(offer.id), "listing_id": str(listing.id)},
        )

    if status_update.status in {OfferStatus.ACCEPTED, OfferStatus.REJECTED, OfferStatus.COUNTERED}:
        # Don't send duplicated notification for ACCEPTED (already sent above)
        if status_update.status != OfferStatus.ACCEPTED:
            notification_type = {
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
            await ws_manager.send_to_user(target_user_id, {
                "type": notification_type.value,
                "offer_id": str(offer.id),
                "listing_id": str(listing.id),
            })

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

    where_cond: Any = Listing.id == offer.listing_id  # type: ignore[arg-type]
    result = await db.execute(select(Listing).where(where_cond))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Bài đăng không tìm thấy")

    if current_user.id != offer.buyer_id and current_user.id != listing.seller_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xem yêu cầu mua này"
        )

    return offer
