"""
CRUD operations for Notification model.

Handles notification creation, retrieval, and management.
"""
import uuid

from sqlalchemy import desc, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.enums import NotificationType
from app.models.notification import Notification


async def get_user_notifications(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20
) -> tuple[list[Notification], int]:
    """Get paginated notifications for a user."""
    # Count total
    count_result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id)  # type: ignore[arg-type]
    )
    total = count_result.scalar_one()

    # Get paginated items
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)  # type: ignore[arg-type]
        .order_by(desc(Notification.created_at))  # type: ignore[arg-type]
        .offset(skip)
        .limit(limit)
    )
    items = list(result.scalars().all())

    return items, total


async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    type: NotificationType | str,
    title: str,
    message: str | None = None,
    data: dict | None = None,
    description: str | None = None,
    related_id: str | None = None,
) -> Notification:
    """Create a notification for a user.

    Backwards-compatible: some callers historically passed `description` or
    `related_id` keys. Normalize to `message` and include `related_id` inside
    `data` when provided.
    """
    notification_type = type
    if isinstance(notification_type, str):
        notification_type = NotificationType(notification_type)

    # Prefer explicit message, otherwise fall back to description
    final_message = message or description or ""

    final_data = dict(data or {})
    if related_id is not None:
        # normalize related id into data payload
        final_data.setdefault("related_id", str(related_id))  # type: ignore[arg-type]

    notification = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        message=final_message,
        data=final_data,
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    return notification


async def get_unread_count(
    db: AsyncSession,
    user_id: uuid.UUID
) -> int:
    """Get count of unread notifications for user."""
    result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.user_id == user_id,  # type: ignore[arg-type]
            Notification.is_read.is_(False)  # type: ignore[arg-type]
        )
    )
    count = result.scalar_one()
    return count


async def get_notification_by_id(
    db: AsyncSession,
    notification_id: uuid.UUID
) -> Notification | None:
    """Get notification by ID."""
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id)  # type: ignore[arg-type]
    )
    return result.scalar_one_or_none()


async def mark_notification_as_read(
    db: AsyncSession,
    notification_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Notification | None:
    """Mark a notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,  # type: ignore[arg-type]
            Notification.user_id == user_id,  # type: ignore[arg-type]
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        return None

    notification.is_read = True
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return notification


async def mark_all_notifications_as_read(
    db: AsyncSession,
    user_id: uuid.UUID
) -> int:
    """Mark all unread notifications as read."""
    result = await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,  # type: ignore[arg-type]
            Notification.is_read.is_(False)  # type: ignore[arg-type]
        )
        .values(is_read=True)
    )
    await db.commit()
    return result.rowcount or 0  # type: ignore[return-value]


async def delete_notification(
    db: AsyncSession,
    notification_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """Delete a notification (only owner can delete)."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,  # type: ignore[arg-type]
            Notification.user_id == user_id,  # type: ignore[arg-type]
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        return False

    await db.delete(notification)
    await db.commit()
    return True
