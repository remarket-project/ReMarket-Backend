import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.websocket_manager import ws_manager
from app.crud import (
    crud_escrow,
    crud_listing,
    crud_notification,
    crud_order,
    crud_order_event,
    crud_user,
    crud_wallet,
)
from app.models.enums import EscrowStatus, ListingStatus, NotificationType, OrderStatus, PaymentMethod, UserRole
from app.schemas.order import OrderDirectCreate, OrderRead, OrderStatusUpdate
from app.services import send_order_completed_email, send_order_created_email

router = APIRouter(prefix="/orders", tags=["Orders"])
limiter = Limiter(key_func=get_remote_address)


class OrderEventRead(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    event_type: str
    detail: str | None = None
    actor_id: uuid.UUID | None = None
    created_at: datetime


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
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Save shipping address if provided
    if data.shipping_address:
        addr = data.shipping_address
        order.shipping_name = addr.name
        order.shipping_phone = addr.phone
        order.shipping_province = addr.province
        order.shipping_district = addr.district
        order.shipping_ward = addr.ward
        order.shipping_address_detail = addr.address_detail
        order.shipping_note = addr.note
        order.shipping_province_id = addr.province_id
        order.shipping_district_id = addr.district_id
        order.shipping_ward_code = addr.ward_code
        db.add(order)

    # Auto-create escrow for direct order flow.
    existing_escrow = await crud_escrow.get_escrow_by_order_id(db, order.id)
    if not existing_escrow:
        buyer_wallet = await crud_wallet.get_or_create_wallet(db, current_user.id)
        seller_wallet = await crud_wallet.get_or_create_wallet(db, listing.seller_id)
        await crud_escrow.create_escrow(
            db=db,
            order_id=order.id,
            amount=order.final_price,
            buyer_wallet_id=buyer_wallet.id,
            seller_wallet_id=seller_wallet.id,
        )

    # Auto-fund escrow if wallet payment
    if data.payment_method == PaymentMethod.WALLET:
        escrow = await crud_escrow.get_escrow_by_order_id(db, order.id)
        if escrow and escrow.status == EscrowStatus.PENDING.value:
            buyer_wallet = await crud_wallet.get_or_create_wallet(db, current_user.id)
            try:
                await crud_wallet.lock_balance(
                    db=db,
                    wallet_id=buyer_wallet.id,
                    amount=escrow.amount,
                    order_id=order.id,
                    description=f"Escrow for order {order.id}",
                )
                await crud_escrow.fund_escrow(db, escrow.id)
            except ValueError as wallet_err:
                # BUG-08 FIX: Báo lỗi rõ ràng thay vì silent pass
                raise HTTPException(
                    status_code=400,
                    detail="Số dư ví không đủ. Vui lòng nạp thêm tiền hoặc chọn COD."
                ) from wallet_err

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
        await ws_manager.send_to_user(rejected_offer.buyer_id, {
            "type": "listing_sold",
            "listing_id": str(listing.id),
        })

    # WS: notify seller about new order
    await ws_manager.send_to_user(listing.seller_id, {
        "type": "new_order",
        "user_id": str(listing.seller_id),
    })

    # WS: order_status_updated for buyer
    await ws_manager.send_to_user(current_user.id, {
        "type": "order_status_updated",
        "order_id": str(order.id),
    })

    return order


@router.get("", response_model=list[OrderRead])
@router.get("/me", response_model=list[OrderRead])
async def get_my_orders(
    current_user: CurrentUser,
    db: SessionDep,
):
    """Lấy danh sách đơn hàng của tôi (là người mua hoặc người bán)"""
    items, total = await crud_order.get_user_orders(db, current_user.id)
    result = []
    for item in items:
        d = {c.name: getattr(item, c.name) for c in item.__table__.columns}
        d["has_dispute"] = len(item.disputes) > 0
        result.append(OrderRead.model_validate(d))
    return result


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


@router.get("/{order_id}/timeline", response_model=list[OrderEventRead])
async def get_order_timeline(
    current_user: CurrentUser,
    db: SessionDep,
    order_id: uuid.UUID,
):
    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Đơn hàng không tìm thấy")

    if order.buyer_id != current_user.id and order.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")

    events = await crud_order_event.get_order_events(db, order_id)
    return [OrderEventRead.model_validate(event) for event in events]


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

    if order.status != OrderStatus.DELIVERED:
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

    # WS events
    await ws_manager.send_to_user(order.buyer_id, {
        "type": "order_status_updated",
        "order_id": str(order.id),
    })
    await ws_manager.send_to_user(order.seller_id, {
        "type": "order_status_updated",
        "order_id": str(order.id),
    })

    return updated_order


@router.post("/{order_id}/accept", response_model=OrderRead)
async def accept_order(
    current_user: CurrentUser,
    db: SessionDep,
    order_id: uuid.UUID,
):
    """Buyer xác nhận đã nhận hàng → complete + release escrow ngay."""
    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Đơn hàng không tìm thấy")

    if order.buyer_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Chỉ người mua mới có thể xác nhận nhận hàng")

    if order.status != OrderStatus.DELIVERED:
        raise HTTPException(
            status_code=400, detail=f"Không thể xác nhận ở trạng thái {order.status}")

    updated_order = await crud_order.complete_order(db, order)

    # WS events
    await ws_manager.send_to_user(order.buyer_id, {
        "type": "order_status_updated",
        "order_id": str(order.id),
    })
    await ws_manager.send_to_user(order.seller_id, {
        "type": "order_status_updated",
        "order_id": str(order.id),
    })

    return updated_order


class ShipOrderInput(BaseModel):
    tracking_number: str | None = None
    shipping_provider: str | None = None


@router.post("/{order_id}/ship", response_model=OrderRead)
async def ship_order(
    current_user: CurrentUser,
    db: SessionDep,
    order_id: uuid.UUID,
    data: ShipOrderInput = ShipOrderInput(),
):
    """Seller đánh dấu đã gửi hàng → PENDING → SHIPPING."""
    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Đơn hàng không tìm thấy")

    if order.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="Chỉ người bán mới có thể xác nhận đã gửi hàng")

    if order.status != OrderStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Không thể gửi hàng ở trạng thái {order.status}")

    order.status = OrderStatus.SHIPPING
    if data.tracking_number:
        order.tracking_number = data.tracking_number
    if data.shipping_provider:
        order.shipping_provider = data.shipping_provider
    order.updated_at = datetime.now(timezone.utc)
    db.add(order)
    await db.commit()
    await db.refresh(order)

    await crud_order_event.create_order_event(
        db, order.id, "SHIPPED_BY_SELLER",
        f"Seller marked as shipped. Tracking: {data.tracking_number or 'N/A'}",
        actor_id=current_user.id,
    )

    await ws_manager.send_to_user(order.buyer_id, {
        "type": "order_status_updated",
        "order_id": str(order.id),
    })

    return order


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
            status_code=400, detail="Chỉ có thể hủy đơn hàng ở trạng thái PENDING")

    updated_order = await crud_order.cancel_order(db, order)

    target_user_id = order.seller_id if current_user.id == order.buyer_id else order.buyer_id
    await crud_notification.create_notification(
        db=db,
        user_id=target_user_id,
        type=NotificationType.ORDER_CANCELLED,
        title="Đơn hàng bị hủy",
        message="Đơn hàng đã bị hủy bởi bên kia.",
        data={"order_id": str(order.id), "listing_id": str(order.listing_id)},
    )

    # WS events
    await ws_manager.send_to_user(order.buyer_id, {
        "type": "order_cancelled",
        "order_id": str(order.id),
    })
    await ws_manager.send_to_user(order.seller_id, {
        "type": "order_cancelled",
        "order_id": str(order.id),
    })
    await ws_manager.send_to_user(order.buyer_id, {
        "type": "order_status_updated",
        "order_id": str(order.id),
    })
    await ws_manager.send_to_user(order.seller_id, {
        "type": "order_status_updated",
        "order_id": str(order.id),
    })

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

    # Only admin can update status
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403, detail="Chỉ admin có thể cập nhật trạng thái đơn hàng")

    # Validate status transitions (admin-only full transitions)
    valid_transitions = {
        OrderStatus.PENDING: [OrderStatus.SHIPPING],
        OrderStatus.SHIPPING: [OrderStatus.DELIVERED, OrderStatus.RETURNING],
        OrderStatus.RETURNING: [OrderStatus.RETURNED],
        OrderStatus.RETURNED: [],
        OrderStatus.DELIVERED: [OrderStatus.COMPLETED],
        OrderStatus.DISPUTED: [OrderStatus.COMPLETED, OrderStatus.RETURNED],
        OrderStatus.COMPLETED: [],
        OrderStatus.CANCELLED: [],
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
    order.updated_at = datetime.now(timezone.utc)
    db.add(order)

    # If DELIVERED, set auto-complete timer
    if data.status == OrderStatus.DELIVERED:
        from datetime import timedelta
        order.delivered_at_record = datetime.now(timezone.utc)
        order.auto_complete_at = order.delivered_at_record + timedelta(hours=settings.ORDER_AUTO_COMPLETE_HOURS)

    await db.commit()
    await db.refresh(order)

    # Send notification to buyer/seller
    status_messages = {
        OrderStatus.SHIPPING: ("Đang vận chuyển", "Đơn hàng đang được vận chuyển"),
        OrderStatus.DELIVERED: ("Đã giao hàng", "Đơn hàng đã được giao hàng"),
        OrderStatus.COMPLETED: ("Đơn hàng hoàn tất", "Đơn hàng đã hoàn tất thành công"),
        OrderStatus.RETURNING: ("Đang hoàn trả", "Đơn hàng đang được hoàn trả"),
        OrderStatus.RETURNED: ("Đã hoàn trả", "Đơn hàng đã hoàn trả thành công"),
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

    # WS events
    await ws_manager.send_to_user(order.buyer_id, {
        "type": "order_status_updated",
        "order_id": str(order.id),
    })
    await ws_manager.send_to_user(order.seller_id, {
        "type": "order_status_updated",
        "order_id": str(order.id),
    })

    return order
