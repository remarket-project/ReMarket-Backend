"""CRUD for saved listings and follows."""
import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.saved_follow import FollowSeller, SavedListing


async def has_saved_listing(
    db: AsyncSession,
    user_id: uuid.UUID,
    listing_id: uuid.UUID,
) -> bool:
    result = await db.execute(
        select(SavedListing).where(
            SavedListing.user_id == user_id,  # type: ignore[arg-type]
            SavedListing.listing_id == listing_id,  # type: ignore[arg-type]
        )
    )
    return result.scalar_one_or_none() is not None


async def save_listing(
    db: AsyncSession,
    user_id: uuid.UUID,
    listing_id: uuid.UUID,
) -> SavedListing:
    result = await db.execute(
        select(SavedListing).where(
            SavedListing.user_id == user_id,  # type: ignore[arg-type]
            SavedListing.listing_id == listing_id,  # type: ignore[arg-type]
        )
    )
    saved = result.scalar_one_or_none()
    if saved:
        return saved

    saved = SavedListing(user_id=user_id, listing_id=listing_id)
    db.add(saved)
    await db.commit()
    await db.refresh(saved)
    return saved


async def unsave_listing(
    db: AsyncSession,
    user_id: uuid.UUID,
    listing_id: uuid.UUID,
) -> bool:
    result = await db.execute(
        select(SavedListing).where(
            SavedListing.user_id == user_id,  # type: ignore[arg-type]
            SavedListing.listing_id == listing_id,  # type: ignore[arg-type]
        )
    )
    saved = result.scalar_one_or_none()
    if not saved:
        return False
    await db.delete(saved)
    await db.commit()
    return True


async def get_saved_listings_by_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[SavedListing], int]:
    total = (
        await db.execute(
            select(func.count()).select_from(SavedListing).where(
                SavedListing.user_id == user_id,  # type: ignore[arg-type]
            )
        )
    ).scalar_one()

    result = await db.execute(
        select(SavedListing)
        .where(SavedListing.user_id == user_id)  # type: ignore[arg-type]
        .order_by(desc(SavedListing.saved_at))
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all()), int(total)


async def get_saved_listing_count(db: AsyncSession, listing_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(SavedListing).where(
            SavedListing.listing_id == listing_id,  # type: ignore[arg-type]
        )
    )
    return int(result.scalar_one())


async def is_following_seller(
    db: AsyncSession,
    follower_id: uuid.UUID,
    followee_id: uuid.UUID,
) -> bool:
    result = await db.execute(
        select(FollowSeller).where(
            FollowSeller.follower_id == follower_id,  # type: ignore[arg-type]
            FollowSeller.followee_id == followee_id,  # type: ignore[arg-type]
        )
    )
    return result.scalar_one_or_none() is not None


async def follow_seller(
    db: AsyncSession,
    follower_id: uuid.UUID,
    followee_id: uuid.UUID,
) -> FollowSeller:
    result = await db.execute(
        select(FollowSeller).where(
            FollowSeller.follower_id == follower_id,  # type: ignore[arg-type]
            FollowSeller.followee_id == followee_id,  # type: ignore[arg-type]
        )
    )
    follow = result.scalar_one_or_none()
    if follow:
        return follow

    follow = FollowSeller(follower_id=follower_id, followee_id=followee_id)
    db.add(follow)
    await db.commit()
    await db.refresh(follow)
    return follow


async def unfollow_seller(
    db: AsyncSession,
    follower_id: uuid.UUID,
    followee_id: uuid.UUID,
) -> bool:
    result = await db.execute(
        select(FollowSeller).where(
            FollowSeller.follower_id == follower_id,  # type: ignore[arg-type]
            FollowSeller.followee_id == followee_id,  # type: ignore[arg-type]
        )
    )
    follow = result.scalar_one_or_none()
    if not follow:
        return False
    await db.delete(follow)
    await db.commit()
    return True


async def get_followed_sellers(
    db: AsyncSession,
    follower_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[FollowSeller], int]:
    total = (
        await db.execute(
            select(func.count()).select_from(FollowSeller).where(
                FollowSeller.follower_id == follower_id,  # type: ignore[arg-type]
            )
        )
    ).scalar_one()

    result = await db.execute(
        select(FollowSeller)
        .where(FollowSeller.follower_id == follower_id)  # type: ignore[arg-type]
        .order_by(desc(FollowSeller.created_at))
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all()), int(total)


async def get_follower_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(FollowSeller).where(
            FollowSeller.followee_id == user_id,  # type: ignore[arg-type]
        )
    )
    return int(result.scalar_one())


async def get_following_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(FollowSeller).where(
            FollowSeller.follower_id == user_id,  # type: ignore[arg-type]
        )
    )
    return int(result.scalar_one())
