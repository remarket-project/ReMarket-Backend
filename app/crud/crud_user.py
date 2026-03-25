"""
CRUD operations for User model.

Pure database operations (no business logic).
"""
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models import User, UserCreate, UserRegister, UserUpdate
from app.core.security import get_password_hash, hash_token


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Get user by email. Returns None if not found."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    """Get user by ID. Returns None if not found."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_refresh_token(
    db: AsyncSession,
    hashed_token: str
) -> Optional[User]:
    """Find user by their hashed refresh token."""
    result = await db.execute(
        select(User).where(User.hashed_refresh_token == hashed_token)
    )
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user_in: UserCreate | UserRegister) -> User:
    """
    Create a new user in database.

    Args:
        db: Database session
        user_in: User creation data

    Returns:
        Created User object
    """
    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        password_hash=get_password_hash(user_in.password),
        phone=getattr(user_in, 'phone', None)
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    user_in: UserUpdate
) -> Optional[User]:
    """
    Update existing user.

    Args:
        db: Database session
        user_id: User ID to update
        user_in: Data to update

    Returns:
        Updated User object
    """
    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    update_data = user_in.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if hasattr(user, field) and value is not None:
            setattr(user, field, value)

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    refresh_token: Optional[str]
) -> None:
    """
    Update user's refresh token (hashed).

    Args:
        db: Database session
        user_id: User ID
        refresh_token: Refresh token (will be hashed). None = revoke token
    """
    user = await get_user_by_id(db, user_id)
    if user:
        if refresh_token:
            user.hashed_refresh_token = hash_token(refresh_token)
        else:
            user.hashed_refresh_token = None
        db.add(user)
        await db.commit()


async def mark_user_email_verified(
    db: AsyncSession,
    email: str
) -> Optional[User]:
    """Mark user email as verified."""
    user = await get_user_by_email(db, email)
    if not user:
        return None

    user.is_email_verified = True
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_users_list(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100
) -> list[User]:
    """Get paginated list of users."""
    result = await db.execute(
        select(User).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def update_user_status(
    db: AsyncSession,
    user_id: uuid.UUID,
    is_active: bool
) -> Optional[User]:
    """Update user active status."""
    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    user.is_active = is_active
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_users_count(db: AsyncSession) -> int:
    """Get total count of users."""
    from sqlalchemy import func
    result = await db.execute(select(func.count()).select_from(User))
    return result.scalar_one()
