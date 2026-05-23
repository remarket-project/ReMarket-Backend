import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep, CurrentAdmin
from app.crud import crud_admin_audit, crud_notification, crud_listing, crud_escrow, crud_wallet, crud_order
from app.crud.crud_listing import get_listing, get_pending_listings
from app.crud.crud_user import get_user_by_id, get_users_list, update_user_status
from app.models.enums import EscrowStatus, ListingStatus, NotificationType, OrderStatus, UserRole
from app.models.listing import Listing
from app.models.order import Order
from app.models.escrow import Escrow
from app.models.user import User
from app.schemas.escrow import ResolveEscrowRequest
from app.schemas.listing import ListingRead
from app.schemas.user import UserMe, UserStatusUpdate

router = APIRouter(prefix="/admin", tags=["Admin"])


async def _log_admin_action(
    db: SessionDep,
    admin_user: User,
    action: str,
    target_type: str,
    target_id: str,
    note: Optional[str] = None,
) -> None:
    await crud_admin_audit.create_admin_audit_log(
        db=db,
        admin_id=admin_user.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        note=note,
    )


@router.get("/dashboard")
async def get_dashboard_stats(
    db: SessionDep,
    admin_user: CurrentAdmin,
):
    """Admin: tổng quan nhanh hệ thống cho dashboard."""
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    total_listings = (await db.execute(select(func.count()).select_from(Listing))).scalar_one()
    total_orders = (await db.execute(select(func.count()).select_from(Order))).scalar_one()
    disputed_escrows = (
        await db.execute(
            select(func.count())
            .select_from(Escrow)
            .where(Escrow.status == EscrowStatus.DISPUTED.value)
        )
    ).scalar_one()

    return {
        "total_users": total_users,
        "total_listings": total_listings,
        "total_orders": total_orders,
        "disputed_escrows": disputed_escrows,
    }


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

    user = await get_user_by_id(db, str(user_id))
    if not user:
        raise HTTPException(
            status_code=404, detail="Người dùng không tìm thấy")

    updated_user = await update_user_status(db, str(user_id), status_data.is_active)
    await _log_admin_action(
        db,
        admin_user,
        action="user_status_updated",
        target_type="user",
        target_id=str(user_id),
        note=f"is_active={status_data.is_active}",
    )
    return updated_user


@router.get("/listings/pending", response_model=list[ListingRead])
async def get_pending_listings_route(
    db: SessionDep,
    admin_user: CurrentAdmin,
    skip: int = 0,
    limit: int = 100
):
    """Admin: Danh sách bài đăng đang chờ duyệt"""
    return await get_pending_listings(db, skip=skip, limit=limit)


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

    images = await crud_listing.get_listing_images(db, str(listing_id))
    if not images:
        raise HTTPException(
            status_code=400,
            detail="Không thể duyệt bài đăng không có ảnh"
        )

    listing.status = ListingStatus.ACTIVE
    listing.rejection_reason = None
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    await crud_notification.create_notification(
        db=db,
        user_id=listing.seller_id,
        type=NotificationType.LISTING_APPROVED,
        title="Bài đăng được duyệt",
        message=f"Bài đăng '{listing.title}' của bạn đã được duyệt.",
        data={"listing_id": str(listing.id)},
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
    reason: Optional[str] = Body(None, embed=True, max_length=500)
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
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

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
    await _log_admin_action(
        db,
        admin_user,
        action="listing_rejected",
        target_type="listing",
        target_id=str(listing.id),
        note=reason,
    )
    return listing


@router.post("/escrows/{order_id}/resolve")
async def resolve_escrow_dispute(
    order_id: uuid.UUID,
    payload: ResolveEscrowRequest,
    admin_user: CurrentAdmin,
    db: SessionDep,
):
    """Admin: resolve disputed escrow by releasing to seller or refunding buyer."""
    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Đơn hàng không tìm thấy")

    escrow = await crud_escrow.get_escrow_by_order_id(db, order_id)
    if not escrow:
        raise HTTPException(status_code=404, detail="Escrow không tìm thấy")

    if payload.result == "release":
        await crud_wallet.transfer_locked_to_user(
            db=db,
            from_wallet_id=escrow.buyer_wallet_id,
            to_wallet_id=escrow.seller_wallet_id,
            amount=escrow.amount,
            order_id=order_id,
            description=f"Admin release escrow for order {order_id}",
        )
    else:
        await crud_wallet.unlock_balance(
            db=db,
            wallet_id=escrow.buyer_wallet_id,
            amount=escrow.amount,
            order_id=order_id,
            description=f"Admin refund escrow for order {order_id}",
        )

    updated_escrow = await crud_escrow.resolve_dispute(
        db=db,
        escrow_id=escrow.id,
        admin_id=admin_user.id,
        resolution=payload.result,
    )

    if payload.result == "release":
        await crud_order.update_order_status(db, order_id, OrderStatus.COMPLETED)
        buyer_title = "Tranh chấp được xử lý"
        buyer_message = "Admin đã xử lý tranh chấp: tiền được giải phóng cho người bán."
        seller_title = "Nhận thanh toán escrow"
        seller_message = "Admin đã xử lý tranh chấp và giải phóng thanh toán cho bạn."
    else:
        await crud_order.update_order_status(db, order_id, OrderStatus.CANCELLED)
        buyer_title = "Hoàn tiền escrow thành công"
        buyer_message = "Admin đã xử lý tranh chấp và hoàn tiền vào ví của bạn."
        seller_title = "Tranh chấp được xử lý"
        seller_message = "Admin đã xử lý tranh chấp: đơn hàng được hoàn tiền cho người mua."

    await crud_notification.create_notification(
        db=db,
        user_id=order.buyer_id,
        type=NotificationType.ORDER_CANCELLED if payload.result == "refund" else NotificationType.ORDER_COMPLETED,
        title=buyer_title,
        message=buyer_message,
        data={"order_id": str(
            order_id), "escrow_result": payload.result, "note": payload.note or ""},
    )
    await crud_notification.create_notification(
        db=db,
        user_id=order.seller_id,
        type=NotificationType.ORDER_COMPLETED if payload.result == "release" else NotificationType.ORDER_CANCELLED,
        title=seller_title,
        message=seller_message,
        data={"order_id": str(
            order_id), "escrow_result": payload.result, "note": payload.note or ""},
    )

    await _log_admin_action(
        db,
        admin_user,
        action=f"escrow_resolved_{payload.result}",
        target_type="escrow",
        target_id=str(order_id),
        note=payload.note,
    )

    return {
        "message": "Escrow dispute resolved",
        "order_id": str(order_id),
        "result": payload.result,
        "escrow_status": updated_escrow.status if updated_escrow else None,
    }
