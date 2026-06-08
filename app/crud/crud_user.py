"""
CRUD operations for User model.

Pure database operations (no business logic).
"""
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.security import get_password_hash, hash_token
from app.models import User, UserCreate, UserRegister, UserUpdate
from app.models.enums import OrderStatus
from app.models.order import Order


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Get user by email. Returns None if not found."""
    result = await db.execute(select(User).where(User.email == email))  # type: ignore[arg-type]
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Get user by ID. Returns None if not found."""
    result = await db.execute(select(User).where(User.id == user_id))  # type: ignore[arg-type]
    return result.scalar_one_or_none()


async def get_user_by_refresh_token(
    db: AsyncSession,
    hashed_token: str
) -> User | None:
    """Find user by their hashed refresh token."""
    result = await db.execute(
        select(User).where(User.hashed_refresh_token == hashed_token)  # type: ignore[arg-type]
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
        phone=getattr(user_in, 'phone', None),
        shop_name=getattr(user_in, 'shop_name', None),
        shop_description=getattr(user_in, 'shop_description', None),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    user_in: UserUpdate
) -> User | None:
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
    refresh_token: str | None
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


async def update_user_password(
    db: AsyncSession,
    user_id: uuid.UUID,
    new_password_hash: str
) -> User | None:
    """
    Update user's password.

    Args:
        db: Database session
        user_id: User ID
        new_password_hash: New password hash

    Returns:
        Updated User object or None if user not found
    """
    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    user.password_hash = new_password_hash
    # Invalidate refresh token for security
    user.hashed_refresh_token = None
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def mark_user_email_verified(
    db: AsyncSession,
    email: str
) -> User | None:
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
) -> User | None:
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


async def update_user_ratings(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """
    Update user ratings based on reviews received.
    Recalculates rating_avg, rating_count, and trust_score.

    Args:
        db: Database session
        user_id: User ID to calculate ratings for

    Returns:
        Updated User object or None if user not found
    """
    from sqlalchemy import func

    from app.models import Review

    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    # Calculate average rating from all reviews where this user is the reviewee
    result = await db.execute(
        select(
            func.avg(Review.rating).label("avg_rating"),
            func.count().label("review_count")
        ).where(Review.reviewee_id == user_id)  # type: ignore[arg-type]
    )
    row = result.one()
    avg_rating = row.avg_rating or 0
    review_count = row.review_count or 0

    # Update user ratings
    user.rating_avg = Decimal(str(round(float(avg_rating), 2))) if avg_rating else Decimal("0.00")
    user.rating_count = review_count

    # Calculate trust_score based on:
    # - Rating average (0-5)
    # - Completed orders (at least 5 for higher trust)
    # - Is email verified
    completed_orders_result = await db.execute(
        select(func.count())
        .select_from(Order)
        .where(
            Order.seller_id == user_id,  # type: ignore[arg-type]
            Order.status == OrderStatus.COMPLETED,  # type: ignore[arg-type]
        )
    )
    completed_orders = completed_orders_result.scalar_one() or 0

    # Trust score calculation: (rating/5) * 0.6 + min(completed_orders/10, 1) * 0.3 + is_email_verified * 0.1
    rating_factor = (float(user.rating_avg) / 5.0) * 0.6
    orders_factor = min(completed_orders / 10.0, 1.0) * 0.3
    email_factor = 0.1 if user.is_email_verified else 0
    trust_score = rating_factor + orders_factor + email_factor
    user.trust_score = Decimal(str(round(trust_score * 100, 1)))  # Convert to percentage

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
