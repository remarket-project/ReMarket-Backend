import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, SessionDep, CurrentAdmin
from app.crud import crud_notification, crud_listing
from app.crud.crud_listing import get_listing, get_pending_listings
from app.crud.crud_user import get_user_by_id, get_users_list, update_user_status
from app.models.enums import ListingStatus, NotificationType, UserRole
from app.models.user import User
from app.schemas.listing import ListingRead
from app.schemas.user import UserMe, UserStatusUpdate

router = APIRouter(prefix="/admin", tags=["Admin"])


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
    return listing
