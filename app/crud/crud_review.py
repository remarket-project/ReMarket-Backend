"""
CRUD operations for Review model.

Handles review creation and retrieval, including user trust score calculations.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.review import Review
from app.models.user import User


def calculate_trust_score(user: User) -> Decimal:
    """
    Calculate trust score based on:
    - completed_orders * 2
    - rating_avg * 10
    - min(account_age_months, 12)
    """
    score = float(user.completed_orders) * 2
    score += float(user.rating_avg) * 10
    account_age_days = (
        datetime.now(timezone.utc) -
        user.created_at.replace(tzinfo=timezone.utc)
    ).days
    account_age_months = account_age_days / 30
    score += min(account_age_months, 12)
    return Decimal(str(round(score, 1)))


async def get_review_by_order(
    db: AsyncSession,
    order_id: uuid.UUID
) -> Review | None:
    """Get first review for an order."""
    result = await db.execute(
        select(Review).where(Review.order_id == order_id)  # type: ignore[arg-type]
    )
    return result.scalar_one_or_none()


async def get_reviews_by_order(
    db: AsyncSession,
    order_id: uuid.UUID
) -> list[Review]:
    """Get all reviews for an order (typically buyer and seller reviews)."""
    result = await db.execute(
        select(Review)
        .where(Review.order_id == order_id)  # type: ignore[arg-type]
        .order_by(asc(Review.created_at))
    )
    return list(result.scalars().all())


async def get_review_by_order_and_reviewer(
    db: AsyncSession,
    order_id: uuid.UUID,
    reviewer_id: uuid.UUID
) -> Review | None:
    """Check if user has already reviewed this order."""
    result = await db.execute(
        select(Review).where(
            and_(
                Review.order_id == order_id,  # type: ignore[arg-type]
                Review.reviewer_id == reviewer_id,  # type: ignore[arg-type]
            )
        )
    )
    return result.scalar_one_or_none()


async def create_review(
    db: AsyncSession,
    order_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    reviewee_id: uuid.UUID,
    rating: int,
    comment: str | None = None
) -> Review:
    """Create a review and update user statistics."""
    review = Review(
        order_id=order_id,
        reviewer_id=reviewer_id,
        reviewee_id=reviewee_id,
        rating=rating,
        comment=comment,
    )
    db.add(review)

    # Update user stats
    result = await db.execute(
        select(User).where(User.id == reviewee_id)  # type: ignore[arg-type]
    )
    user = result.scalar_one_or_none()

    if user:
        old_avg = float(user.rating_avg)
        old_count = user.rating_count
        new_count = old_count + 1
        new_avg = ((old_avg * old_count) + rating) / new_count
        user.rating_count = new_count
        user.rating_avg = Decimal(str(round(new_avg, 2)))
        # Calculate and update trust_score
        user.trust_score = calculate_trust_score(user)

    await db.commit()
    await db.refresh(review)
    return review


async def get_user_reviews(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20
) -> tuple[list[Review], int]:
    """Get paginated reviews for a user."""
    from sqlalchemy import func

    # Count total
    count_result = await db.execute(
        select(func.count())
        .select_from(Review)
        .where(Review.reviewee_id == user_id)  # type: ignore[arg-type]
    )
    total = count_result.scalar_one()

    # Get paginated items
    result = await db.execute(
        select(Review)
        .where(Review.reviewee_id == user_id)  # type: ignore[arg-type]
        .order_by(desc(Review.created_at))
        .offset(skip)
        .limit(limit)
    )
    items = list(result.scalars().all())

    return items, total
