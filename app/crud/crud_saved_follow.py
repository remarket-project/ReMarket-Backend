"""CRUD for saved listings and follows."""
import uuid
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.saved_follow import SavedListing, FollowSeller


async def save_listing(db: AsyncSession, user_id: uuid.UUID, listing_id: uuid.UUID) -> SavedListing:
    s = SavedListing(user_id=user_id, listing_id=listing_id)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


async def unsave_listing(db: AsyncSession, user_id: uuid.UUID, listing_id: uuid.UUID) -> bool:
    result = await db.execute(select(SavedListing).where(SavedListing.user_id == user_id, SavedListing.listing_id == listing_id))
    s = result.scalar_one_or_none()
    if not s:
        return False
    await db.delete(s)
    await db.commit()
    return True


async def follow_seller(db: AsyncSession, follower_id: uuid.UUID, followee_id: uuid.UUID) -> FollowSeller:
    f = FollowSeller(follower_id=follower_id, followee_id=followee_id)
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return f


async def unfollow_seller(db: AsyncSession, follower_id: uuid.UUID, followee_id: uuid.UUID) -> bool:
    result = await db.execute(select(FollowSeller).where(FollowSeller.follower_id == follower_id, FollowSeller.followee_id == followee_id))
    f = result.scalar_one_or_none()
    if not f:
        return False
    await db.delete(f)
    await db.commit()
    return True
