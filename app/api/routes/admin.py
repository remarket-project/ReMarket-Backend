import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, HTTPException, status
from sqlalchemy import desc, func, select

from app.core.config import settings
from app.core.websocket_manager import ws_manager
from app.api.deps import CurrentAdmin, SessionDep
from app.crud import (
    crud_admin_audit,
    crud_dispute,
    crud_escrow,
    crud_notification,
    crud_order,
    crud_wallet,
)
from app.crud.crud_listing import get_listing, get_images_for_listings, get_pending_listings
from app.crud.crud_user import get_user_by_id, get_users_list, update_user_status, get_admin_user_ids
from app.models.enums import (
    EscrowStatus,
    ListingStatus,
    NotificationType,
    OrderStatus,
)
from app.models.escrow import Escrow
from app.models.listing import Listing
from app.models.order import Order
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.schemas.dispute import DisputeRead
from app.schemas.escrow import ResolveEscrowRequest
from app.schemas.listing import ListingRead, ListingWithImages
from app.schemas.user import UserMe, UserStatusUpdate
from app.services import stripe_connect

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])



async def _log_admin_action(
    db: SessionDep,
    admin_user: User,
    action: str,
    target_type: str,
    target_id: str,
    note: str | None = None,
) -> None:
    await crud_admin_audit.create_admin_audit_log(
        db=db,
        admin_id=admin_user.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        note=note,
    )


async def _broadcast_to_admins(db: SessionDep, message: dict) -> None:
    """Helper: gửi WebSocket message đến tất cả admin đang online."""
    admin_ids = await get_admin_user_ids(db)
    if admin_ids:
        await ws_manager.broadcast_to_users(admin_ids, message)


@router.get("/dashboard")
async def get_dashboard_stats(
    db: SessionDep,
    admin_user: CurrentAdmin,
):
    """Admin: tổng quan nhanh hệ thống cho dashboard."""
    from app.core.cache import stats_cache

    cache_key = "admin_dashboard_stats"
    if cached := stats_cache.get(cache_key):
        return cached

    import asyncio
    from app.models.dispute import Dispute

    count_users = db.execute(select(func.count()).select_from(User))
    count_listings = db.execute(select(func.count()).select_from(Listing))
    count_orders = db.execute(select(func.count()).select_from(Order))
    count_disputes = db.execute(
        select(func.count()).select_from(Dispute).where(Dispute.status == "open")
    )

    results = await asyncio.gather(
        count_users, count_listings, count_orders, count_disputes,
    )

    stats = {
        "total_users": results[0].scalar_one(),
        "total_listings": results[1].scalar_one(),
        "total_orders": results[2].scalar_one(),
        "disputed_escrows": results[3].scalar_one(),
    }

    stats_cache[cache_key] = stats
    return stats


@router.get("/users", response_model=list[UserMe])
async def list_users(
    db: SessionDep,
    admin_user: CurrentAdmin,
    skip: int = 0,
    limit: int = 100
):
    """Admin: Danh sách tất cả người dùng"""
    users = await get_users_list(db, skip=skip, limit=limit)
    return users


@router.patch("/users/{user_id}/status", response_model=UserMe)
async def update_user_account_status(
    user_id: uuid.UUID,
    status_data: UserStatusUpdate,
    admin_user: CurrentAdmin,
    db: SessionDep
):
    """Admin: Khóa hoặc mở khóa người dùng"""
    if str(user_id) == str(admin_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bạn không thể thay đổi trạng thái của chính mình"
        )

    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Người dùng không tìm thấy")

    updated_user = await update_user_status(db, user_id, status_data.is_active)
    await _log_admin_action(
        db,
        admin_user,
        action="user_status_updated",
        target_type="user",
        target_id=str(user_id),
        note=f"is_active={status_data.is_active}",
    )
    return updated_user


@router.get("/listings/pending", response_model=list[ListingWithImages])
async def get_pending_listings_route(
    db: SessionDep,
    admin_user: CurrentAdmin,
    skip: int = 0,
    limit: int = 100
):
    """Admin: Danh sách bài đăng đang chờ duyệt"""
    listings = await get_pending_listings(db, skip=skip, limit=limit)

    listing_ids = [item.id for item in listings]
    images_by_listing = await get_images_for_listings(db, listing_ids)

    result = []
    for item in listings:
        listing_dict = item.model_dump()
        listing_dict["images"] = images_by_listing.get(item.id, [])
        if getattr(item, "seller", None):
            listing_dict["seller_name"] = item.seller.full_name
            listing_dict["seller_avatar_url"] = item.seller.avatar_url
        result.append(ListingWithImages(**listing_dict))

    return result


@router.post("/listings/{listing_id}/approve", response_model=ListingRead)
async def approve_listing(
    listing_id: uuid.UUID,
    admin_user: CurrentAdmin,
    db: SessionDep
):
    """Admin: Duyệt bài đăng"""
    listing = await get_listing(db, str(listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Bài đăng không tìm thấy")

    if listing.status != ListingStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Chỉ có thể duyệt bài đăng PENDING. Trạng thái hiện tại: {listing.status}"
        )

    listing.status = ListingStatus.ACTIVE
    listing.rejection_reason = None
    listing.updated_at = datetime.now(timezone.utc)
    db.add(listing)
    await db.commit()
    await crud_notification.create_notification(
        db=db,
        user_id=listing.seller_id,
        type=NotificationType.LISTING_APPROVED,
        title="Bài đăng được duyệt",
        message=f"Bài đăng '{listing.title}' của bạn đã được duyệt.",
        data={"listing_id": str(listing.id)},
    )
    await ws_manager.send_to_user(
        listing.seller_id,
        {"type": "listing_approved", "listing_id": str(listing.id)},
    )
    await ws_manager.broadcast_to_all(
        {"type": "listing_approved_broadcast", "listing_id": str(listing.id)},
    )
    await _log_admin_action(
        db,
        admin_user,
        action="listing_approved",
        target_type="listing",
        target_id=str(listing.id),
    )
    return listing


@router.post("/listings/{listing_id}/reject", response_model=ListingRead)
async def reject_listing_route(
    listing_id: uuid.UUID,
    admin_user: CurrentAdmin,
    db: SessionDep,
    reason: str | None = Body(None, embed=True, max_length=500)
):
    """Admin: Từ chối bài đăng"""
    listing = await get_listing(db, str(listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Bài đăng không tìm thấy")

    if listing.status != ListingStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Chỉ có thể từ chối bài đăng PENDING. Trạng thái hiện tại: {listing.status}"
        )

    listing.status = ListingStatus.REJECTED
    listing.rejection_reason = reason
    listing.updated_at = datetime.now(timezone.utc)
    db.add(listing)
    await db.commit()

    message = f"Bài đăng '{listing.title}' của bạn đã bị từ chối."
    if reason:
        message += f" Lý do: {reason}"

    await crud_notification.create_notification(
        db=db,
        user_id=listing.seller_id,
        type=NotificationType.LISTING_REJECTED,
        title="Bài đăng bị từ chối",
        message=message,
        data={"listing_id": str(listing.id), "reason": reason or ""},
    )
    await ws_manager.send_to_user(
        listing.seller_id,
        {"type": "listing_rejected", "listing_id": str(listing.id), "reason": reason or ""},
    )
    await ws_manager.broadcast_to_all({"type": "listing_rejected_broadcast"})
    await _log_admin_action(
        db,
        admin_user,
        action="listing_rejected",
        target_type="listing",
        target_id=str(listing.id),
        note=reason,
    )
    return listing


@router.post("/disputes/{dispute_id}/resolve")
async def resolve_dispute(
    dispute_id: uuid.UUID,
    payload: ResolveEscrowRequest,
    admin_user: CurrentAdmin,
    db: SessionDep,
):
    """Admin: resolve a dispute by ID."""
    dispute = await crud_dispute.get_dispute_by_id(db, dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    if dispute.status != "open":
        raise HTTPException(status_code=400, detail=f"Dispute is already {dispute.status}")

    await crud_dispute.resolve_dispute(
        db=db,
        dispute_id=dispute.id,
        resolved_by=admin_user.id,
        resolution=payload.result,
        admin_notes=payload.note,
    )

    order = await crud_order.get_order_by_id(db, dispute.order_id)

    if payload.result == "release":
        buyer_title = "Tranh chấp được xử lý"
        buyer_message = "Admin đã xử lý tranh chấp: tiền được giải phóng cho người bán."
        seller_title = "Nhận thanh toán"
        seller_message = "Admin đã xử lý tranh chấp và giải phóng thanh toán cho bạn."
    else:
        buyer_title = "Hoàn tiền thành công"
        buyer_message = "Admin đã xử lý tranh chấp và hoàn tiền vào ví của bạn."
        seller_title = "Tranh chấp được xử lý"
        seller_message = "Admin đã xử lý tranh chấp: đơn hàng được hoàn tiền cho người mua."

    if order:
        await crud_notification.create_notification(
            db=db, user_id=order.buyer_id,
            type=NotificationType.DISPUTE_RESOLVED,
            title=buyer_title, message=buyer_message,
            data={"order_id": str(dispute.order_id), "result": payload.result, "note": payload.note or ""},
        )
        await crud_notification.create_notification(
            db=db, user_id=order.seller_id,
            type=NotificationType.DISPUTE_RESOLVED,
            title=seller_title, message=seller_message,
            data={"order_id": str(dispute.order_id), "result": payload.result, "note": payload.note or ""},
        )

    await _log_admin_action(
        db, admin_user,
        action=f"dispute_resolved_{payload.result}",
        target_type="dispute",
        target_id=str(dispute.id),
        note=payload.note,
    )

    if order:
        await ws_manager.send_to_user(order.buyer_id, {
            "type": "order_status_updated", "order_id": str(dispute.order_id),
        })
        await ws_manager.send_to_user(order.seller_id, {
            "type": "order_status_updated", "order_id": str(dispute.order_id),
        })
        await _broadcast_to_admins(db, {
            "type": "order_status_updated", "order_id": str(dispute.order_id),
        })

    return {
        "message": "Dispute resolved",
        "dispute_id": str(dispute.id),
        "order_id": str(dispute.order_id),
        "result": payload.result,
    }


# ============================================================================
# Admin Order Management
# ============================================================================

@router.get("/orders")
async def admin_list_orders(
    db: SessionDep,
    admin_user: CurrentAdmin,
    status: str | None = None,
    skip: int = 0,
    limit: int = 20,
):
    """Admin: list all orders, filter by status."""
    if status:
        result = await db.execute(
            select(Order).where(Order.status == status)  # type: ignore[arg-type]
            .order_by(desc(Order.created_at)).offset(skip).limit(limit)  # type: ignore[arg-type]
        )
        count_result = await db.execute(
            select(func.count()).select_from(Order)
            .where(Order.status == status)  # type: ignore[arg-type]
        )
    else:
        result = await db.execute(
            select(Order).order_by(desc(Order.created_at)).offset(skip).limit(limit)  # type: ignore[arg-type]
        )
        count_result = await db.execute(select(func.count()).select_from(Order))

    items = list(result.scalars().all())
    total = count_result.scalar_one()

    return {"items": items, "total": total}


@router.post("/orders/{order_id}/ship")
async def admin_ship_order(
    order_id: uuid.UUID,
    admin_user: CurrentAdmin,
    db: SessionDep,
):
    """Admin: PENDING → SHIPPING"""
    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Cannot ship order with status {order.status}")

    updated = await crud_order.update_order_status(db, order_id, OrderStatus.SHIPPING)
    await _log_admin_action(db, admin_user, "order_shipped", "order", str(order_id))

    await ws_manager.send_to_user(order.buyer_id, {
        "type": "order_status_updated", "order_id": str(order_id),
    })
    await ws_manager.send_to_user(order.seller_id, {
        "type": "order_status_updated", "order_id": str(order_id),
    })
    await _broadcast_to_admins(db, {
        "type": "order_status_updated", "order_id": str(order_id),
    })

    return updated


@router.post("/orders/{order_id}/deliver")
async def admin_deliver_order(
    order_id: uuid.UUID,
    admin_user: CurrentAdmin,
    db: SessionDep,
):
    """Admin: SHIPPING → DELIVERED (set auto-complete timer)"""
    from datetime import timedelta

    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.SHIPPING:
        raise HTTPException(status_code=400, detail=f"Cannot deliver order with status {order.status}")

    order.status = OrderStatus.DELIVERED
    order.delivered_at_record = datetime.now(timezone.utc)
    order.auto_complete_at = order.delivered_at_record + timedelta(hours=settings.ORDER_AUTO_COMPLETE_HOURS)
    order.updated_at = datetime.now(timezone.utc)
    db.add(order)
    await db.commit()
    await db.refresh(order)

    await _log_admin_action(db, admin_user, "order_delivered", "order", str(order_id))

    await crud_notification.create_notification(
        db=db, user_id=order.buyer_id,
        type=NotificationType.SHIPPING_DELIVERED,
        title="Đã giao hàng",
        message=f"Đơn hàng #{str(order_id)[:8]} đã được giao.",
    )
    await ws_manager.send_to_user(order.buyer_id, {
        "type": "order_status_updated", "order_id": str(order_id),
    })
    await ws_manager.send_to_user(order.seller_id, {
        "type": "order_status_updated", "order_id": str(order_id),
    })
    await _broadcast_to_admins(db, {
        "type": "order_status_updated", "order_id": str(order_id),
    })

    return order


@router.post("/orders/{order_id}/return")
async def admin_return_order(
    order_id: uuid.UUID,
    admin_user: CurrentAdmin,
    db: SessionDep,
):
    """Admin: SHIPPING → RETURNING"""
    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.SHIPPING:
        raise HTTPException(status_code=400, detail=f"Cannot return order with status {order.status}")

    updated = await crud_order.update_order_status(db, order_id, OrderStatus.RETURNING)
    await _log_admin_action(db, admin_user, "order_return_initiated", "order", str(order_id))

    await ws_manager.send_to_user(order.buyer_id, {
        "type": "order_status_updated", "order_id": str(order_id),
    })
    await ws_manager.send_to_user(order.seller_id, {
        "type": "order_status_updated", "order_id": str(order_id),
    })
    await _broadcast_to_admins(db, {
        "type": "order_status_updated", "order_id": str(order_id),
    })

    return updated


@router.post("/orders/{order_id}/returned")
async def admin_returned_order(
    order_id: uuid.UUID,
    admin_user: CurrentAdmin,
    db: SessionDep,
):
    """Admin: RETURNING → RETURNED (auto refund escrow)"""
    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.RETURNING:
        raise HTTPException(status_code=400, detail=f"Cannot confirm return with status {order.status}")

    updated = await crud_order.refund_order(db, order)
    await _log_admin_action(db, admin_user, "order_returned", "order", str(order_id))

    await crud_notification.create_notification(
        db=db, user_id=order.buyer_id,
        type=NotificationType.RETURN_CONFIRMED,
        title="Hoàn trả thành công",
        message=f"Đơn hàng #{str(order_id)[:8]} đã được hoàn trả. Tiền đã hoàn lại.",
    )
    await ws_manager.send_to_user(order.buyer_id, {
        "type": "order_status_updated", "order_id": str(order_id),
    })
    await ws_manager.send_to_user(order.seller_id, {
        "type": "order_status_updated", "order_id": str(order_id),
    })
    await _broadcast_to_admins(db, {
        "type": "order_status_updated", "order_id": str(order_id),
    })

    return updated


@router.post("/orders/{order_id}/force-complete")
async def admin_force_complete(
    order_id: uuid.UUID,
    admin_user: CurrentAdmin,
    db: SessionDep,
):
    """Admin: force COMPLETED (any status) + release escrow."""
    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    updated = await crud_order.complete_order(db, order)
    await _log_admin_action(db, admin_user, "order_force_completed", "order", str(order_id))

    await ws_manager.send_to_user(order.buyer_id, {
        "type": "order_status_updated", "order_id": str(order_id),
    })
    await ws_manager.send_to_user(order.seller_id, {
        "type": "order_status_updated", "order_id": str(order_id),
    })
    await _broadcast_to_admins(db, {
        "type": "order_status_updated", "order_id": str(order_id),
    })

    return updated


@router.post("/orders/{order_id}/force-cancel")
async def admin_force_cancel(
    order_id: uuid.UUID,
    admin_user: CurrentAdmin,
    db: SessionDep,
):
    """Admin: force CANCELLED + refund escrow."""
    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    updated = await crud_order.cancel_order(db, order)
    await _log_admin_action(db, admin_user, "order_force_cancelled", "order", str(order_id))

    await ws_manager.send_to_user(order.buyer_id, {
        "type": "order_cancelled", "order_id": str(order_id),
    })
    await ws_manager.send_to_user(order.seller_id, {
        "type": "order_cancelled", "order_id": str(order_id),
    })
    await _broadcast_to_admins(db, {
        "type": "order_cancelled", "order_id": str(order_id),
    })
    await ws_manager.send_to_user(order.buyer_id, {
        "type": "order_status_updated", "order_id": str(order_id),
    })
    await ws_manager.send_to_user(order.seller_id, {
        "type": "order_status_updated", "order_id": str(order_id),
    })
    await _broadcast_to_admins(db, {
        "type": "order_status_updated", "order_id": str(order_id),
    })

    return updated


# ============================================================================
# Admin Dispute Management
# ============================================================================

@router.get("/disputes")
async def admin_list_disputes(
    db: SessionDep,
    admin_user: CurrentAdmin,
    status: str | None = "open",
    skip: int = 0,
    limit: int = 20,
):
    """Admin: list disputes, filter by status."""
    disputes, total = await crud_dispute.list_disputes(db, status=status, skip=skip, limit=limit)
    return {"items": [DisputeRead.model_validate(d) for d in disputes], "total": total}


@router.get("/disputes/{dispute_id}", response_model=DisputeRead)
async def admin_get_dispute(
    dispute_id: uuid.UUID,
    admin_user: CurrentAdmin,
    db: SessionDep,
):
    """Admin: get dispute detail."""
    dispute = await crud_dispute.get_dispute_by_id(db, dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    return dispute
