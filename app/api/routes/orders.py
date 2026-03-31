import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import CurrentUser, SessionDep
from app.crud import crud_listing, crud_notification, crud_order, crud_user
from app.models.enums import ListingStatus, OrderStatus, NotificationType
from app.models.user import User
from app.schemas.order import OrderDirectCreate, OrderRead, OrderStatusUpdate
from app.services import send_order_created_email, send_order_completed_email

router = APIRouter(prefix="/orders", tags=["Orders"])
limiter = Limiter(key_func=get_remote_address)


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/hour")
async def create_direct_order(
    current_user: CurrentUser,
    db: SessionDep,
    request: Request,
    data: OrderDirectCreate,
):
    """Tạo đơn hàng trực tiếp (Mua Ngay)"""
    listing = await crud_listing.get_listing(db, str(data.listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Bài đăng không tìm thấy")
    if listing.status != ListingStatus.ACTIVE:
        raise HTTPException(
            status_code=400, detail="Bài đăng không có sẵn để mua")
    if listing.seller_id == current_user.id:
        raise HTTPException(
            status_code=400, detail="Không thể mua bài đăng của chính mình")

    try:
        order, rejected_offers = await crud_order.create_direct_order(db, current_user.id, listing)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Gửi email
    buyer = await crud_user.get_user_by_id(db, current_user.id)
    seller = await crud_user.get_user_by_id(db, listing.seller_id)
    if buyer and seller:
        await send_order_created_email(buyer=buyer, seller=seller, order=order, listing_title=listing.title)

    # Notify seller about new order
    await crud_notification.create_notification(
        db=db,
        user_id=listing.seller_id,
        type=NotificationType.ORDER_CREATED,
        title="Đơn hàng mới được tạo",
        message=f"Một người mua đã đặt hàng cho bài đăng '{listing.title}'.",
        data={"order_id": str(order.id), "listing_id": str(listing.id)},
    )

    # Notify buyer about order creation
    await crud_notification.create_notification(
        db=db,
        user_id=current_user.id,
        type=NotificationType.ORDER_CREATED,
        title="Đơn hàng được tạo",
        message=f"Đơn hàng của bạn cho '{listing.title}' đã được tạo thành công.",
        data={"order_id": str(order.id), "listing_id": str(listing.id)},
    )

    # Notify other buyers whose offers were rejected due to Buy Now
    for rejected_offer in rejected_offers:
        await crud_notification.create_notification(
            db=db,
            user_id=rejected_offer.buyer_id,
            type=NotificationType.OFFER_REJECTED,
            title="Yêu cầu mua bị từ chối",
            message=f"Yêu cầu mua của bạn cho '{listing.title}' đã bị từ chối vì hàng đã được mua bởi người khác.",
            data={"offer_id": str(rejected_offer.id),
                  "listing_id": str(listing.id)},
        )

    return order


@router.get("", response_model=List[OrderRead])
@router.get("/me", response_model=List[OrderRead])
async def get_my_orders(
    current_user: CurrentUser,
    db: SessionDep,
):
    """Lấy danh sách đơn hàng của tôi (là người mua hoặc người bán)"""
    items, total = await crud_order.get_user_orders(db, current_user.id)
    return items


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    current_user: CurrentUser,
    db: SessionDep,
    order_id: uuid.UUID,
):
    """Lấy chi tiết đơn hàng"""
    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Đơn hàng không tìm thấy")

    if order.buyer_id != current_user.id and order.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")

    return order


@router.post("/{order_id}/complete", response_model=OrderRead)
async def complete_order(
    current_user: CurrentUser,
    db: SessionDep,
    order_id: uuid.UUID,
):
    """Hoàn thành đơn hàng"""
    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Đơn hàng không tìm thấy")

    if order.buyer_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Chỉ người mua mới có thể hoàn thành đơn hàng")

    if order.status != OrderStatus.PENDING:
        raise HTTPException(
            status_code=400, detail=f"Không thể hoàn thành đơn hàng ở trạng thái {order.status}")

    updated_order = await crud_order.complete_order(db, order)

    # Gửi email
    buyer = await crud_user.get_user_by_id(db, order.buyer_id)
    seller = await crud_user.get_user_by_id(db, order.seller_id)
    if buyer and seller:
        await send_order_completed_email(buyer=buyer, seller=seller, order=updated_order)

    # Notify seller
    await crud_notification.create_notification(
        db=db,
        user_id=order.seller_id,
        type=NotificationType.ORDER_COMPLETED,
        title="Đơn hàng hoàn thành",
        message="Người mua đã đánh dấu đơn hàng là hoàn thành.",
        data={"order_id": str(order.id), "listing_id": str(order.listing_id)},
    )

    # Notify buyer
    await crud_notification.create_notification(
        db=db,
        user_id=order.buyer_id,
        type=NotificationType.ORDER_COMPLETED,
        title="Đơn hàng hoàn thành",
        message="Đơn hàng của bạn đã được đánh dấu là hoàn thành.",
        data={"order_id": str(order.id), "listing_id": str(order.listing_id)},
    )

    return updated_order


@router.post("/{order_id}/cancel", response_model=OrderRead)
async def cancel_order(
    current_user: CurrentUser,
    db: SessionDep,
    order_id: uuid.UUID,
):
    """Hủy đơn hàng"""
    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Đơn hàng không tìm thấy")

    if order.buyer_id != current_user.id and order.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")

    if order.status != OrderStatus.PENDING:
        raise HTTPException(
            status_code=400, detail=f"Không thể hủy đơn hàng ở trạng thái {order.status}")

    updated_order = await crud_order.cancel_order(db, order)

    # Revert listing status from SOLD back to ACTIVE if needed
    listing = await crud_listing.get_listing(db, str(order.listing_id))
    if listing and listing.status == ListingStatus.SOLD:
        listing.status = ListingStatus.ACTIVE
        db.add(listing)
        await db.commit()

    target_user_id = order.seller_id if current_user.id == order.buyer_id else order.buyer_id
    await crud_notification.create_notification(
        db=db,
        user_id=target_user_id,
        type=NotificationType.ORDER_CANCELLED,
        title="Đơn hàng bị hủy",
        message="Đơn hàng đã bị hủy bởi bên kia.",
        data={"order_id": str(order.id), "listing_id": str(order.listing_id)},
    )
    return updated_order


@router.patch("/{order_id}/status", response_model=OrderRead)
async def update_order_status(
    current_user: CurrentUser,
    db: SessionDep,
    order_id: uuid.UUID,
    data: OrderStatusUpdate,
):
    """Cập nhật trạng thái đơn hàng"""
    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Đơn hàng không tìm thấy")

    # Only seller can update status
    if order.seller_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Chỉ người bán có thể cập nhật trạng thái")

    # Validate status transitions
    valid_transitions = {
        OrderStatus.PENDING: [OrderStatus.CONFIRMED],
        OrderStatus.CONFIRMED: [OrderStatus.SHIPPING],
        OrderStatus.SHIPPING: [OrderStatus.DELIVERED],
        OrderStatus.DELIVERED: [OrderStatus.COMPLETED],
    }

    if order.status not in valid_transitions:
        raise HTTPException(
            status_code=400,
            detail=f"Không thể chuyển đổi từ trạng thái {order.status}"
        )

    if data.status not in valid_transitions[order.status]:
        raise HTTPException(
            status_code=400,
            detail=f"Không thể chuyển từ {order.status} sang {data.status}"
        )

    # Update order status
    order.status = data.status
    db.add(order)
    await db.commit()
    await db.refresh(order)

    # Send notification to buyer
    status_messages = {
        OrderStatus.CONFIRMED: ("Đơn hàng đã xác nhận", "Người bán đã xác nhận đơn hàng của bạn"),
        OrderStatus.SHIPPING: ("Đang vận chuyển", "Đơn hàng đang được vận chuyển"),
        OrderStatus.DELIVERED: ("Đã giao hàng", "Đơn hàng đã được giao hàng"),
        OrderStatus.COMPLETED: ("Đơn hàng hoàn tất", "Đơn hàng đã hoàn tất thành công"),
    }

    if data.status in status_messages:
        title, message = status_messages[data.status]
        await crud_notification.create_notification(
            db=db,
            user_id=order.buyer_id,
            type=NotificationType.ORDER_STATUS_UPDATED,
            title=title,
            message=message,
            data={"order_id": str(order.id), "status": data.status},
        )

    return order
