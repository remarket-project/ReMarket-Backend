import uuid
from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.models.user import User
from app.schemas.notification import NotificationRead
from app.crud import crud_notification

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class NotificationsPaginated(BaseModel):
    """Phản hồi thông báo có phân trang"""
    items: List[NotificationRead]
    total: int
    page: int
    page_size: int
    total_pages: int


@router.get("/", response_model=NotificationsPaginated)
async def get_my_notifications(
    current_user: CurrentUser,
    db: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """Danh sách thông báo của tôi (có phân trang)"""
    items, total = await crud_notification.get_user_notifications(db, current_user.id, skip, limit)
    return NotificationsPaginated(
        items=items,
        total=total,
        page=(skip // limit) + 1,
        page_size=limit,
        total_pages=((total + limit - 1) // limit) if total > 0 else 0
    )


@router.get("/unread-count")
async def get_unread_notifications_count(
    current_user: CurrentUser,
    db: SessionDep,
):
    """Số lượng thông báo chưa đọc"""
    unread_count = await crud_notification.get_unread_count(db, current_user.id)
    return {"unread_count": unread_count}


@router.put("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_as_read(
    current_user: CurrentUser,
    db: SessionDep,
    notification_id: uuid.UUID,
):
    """Đánh dấu thông báo là đã đọc"""
    notification = await crud_notification.mark_notification_as_read(
        db,
        notification_id,
        current_user.id,
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Thông báo không tìm thấy")
    return notification


@router.put("/read-all")
async def mark_all_notifications_as_read(
    current_user: CurrentUser,
    db: SessionDep,
):
    """Đánh dấu tất cả thông báo là đã đọc"""
    updated_count = await crud_notification.mark_all_notifications_as_read(db, current_user.id)
    return {"updated_count": updated_count}
