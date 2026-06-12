"""Saved listings and follow seller endpoints."""
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import CurrentUser, SessionDep
from app.crud import crud_listing, crud_saved_follow, crud_user
from app.models.enums import ListingStatus
from app.models.listing import Listing
from app.models.user import UserPublic
from app.schemas.listing import ListingWithImages

router = APIRouter(tags=["Social"])
limiter = Limiter(key_func=get_remote_address)


class SavedListingItem(BaseModel):
    saved_at: datetime
    listing: ListingWithImages


class SavedListingCollection(BaseModel):
    items: list[SavedListingItem]
    total: int
    skip: int
    limit: int


class FollowedSellerItem(BaseModel):
    created_at: datetime
    seller: UserPublic


class FollowedSellerCollection(BaseModel):
    items: list[FollowedSellerItem]
    total: int
    skip: int
    limit: int


def _listing_payload(listing: Listing, images) -> ListingWithImages:
    listing_dict = listing.model_dump()
    listing_dict["images"] = images
    return ListingWithImages(**listing_dict)


@router.get("/saved-listings", response_model=SavedListingCollection)
async def list_saved_listings(
    current_user: CurrentUser,
    db: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    saved_items, total = await crud_saved_follow.get_saved_listings_by_user(db, current_user.id, skip=skip, limit=limit)
    listing_ids = [item.listing_id for item in saved_items]
    images_by_listing = await crud_listing.get_images_for_listings(db, listing_ids)

    items = []
    for saved in saved_items:
        listing = await crud_listing.get_listing(db, str(saved.listing_id))
        if listing:
            items.append(
                SavedListingItem(
                    saved_at=saved.saved_at,
                    listing=_listing_payload(
                        listing, images_by_listing.get(saved.listing_id, [])),
                )
            )

    return SavedListingCollection(items=items, total=total, skip=skip, limit=limit)


@router.post("/saved-listings/{listing_id}", response_model=SavedListingItem, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def save_listing(
    listing_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: SessionDep,
):
    listing = await crud_listing.get_listing(db, str(listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Bài đăng không tìm thấy")

    if listing.status not in {ListingStatus.ACTIVE, ListingStatus.SOLD}:
        raise HTTPException(
            status_code=400, detail="Không thể lưu bài đăng chưa được công khai")

    saved = await crud_saved_follow.save_listing(db, current_user.id, listing_id)
    listing.save_count = await crud_saved_follow.get_saved_listing_count(db, listing_id)
    db.add(listing)
    await db.commit()

    images = await crud_listing.get_listing_images(db, str(listing.id))
    return SavedListingItem(saved_at=saved.saved_at, listing=_listing_payload(listing, images))


@router.delete("/saved-listings/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def unsave_listing(
    listing_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: SessionDep,
):
    removed = await crud_saved_follow.unsave_listing(db, current_user.id, listing_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Bài đăng chưa được lưu")

    listing = await crud_listing.get_listing(db, str(listing_id))
    if listing:
        listing.save_count = await crud_saved_follow.get_saved_listing_count(db, listing_id)
        db.add(listing)
        await db.commit()
    return None


@router.get("/followed-sellers", response_model=FollowedSellerCollection)
async def list_followed_sellers(
    current_user: CurrentUser,
    db: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    follows, total = await crud_saved_follow.get_followed_sellers(db, current_user.id, skip=skip, limit=limit)
    items = []
    for follow in follows:
        seller = await crud_user.get_user_by_id(db, follow.followee_id)
        if seller:
            items.append(FollowedSellerItem(
                created_at=follow.created_at, seller=UserPublic.model_validate(seller)))
    return FollowedSellerCollection(items=items, total=total, skip=skip, limit=limit)


@router.post("/followed-sellers/{seller_id}", response_model=FollowedSellerItem, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def follow_seller(
    seller_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: SessionDep,
):
    if seller_id == current_user.id:
        raise HTTPException(
            status_code=400, detail="Không thể tự theo dõi chính mình")

    seller = await crud_user.get_user_by_id(db, seller_id)
    if not seller:
        raise HTTPException(status_code=404, detail="Người bán không tìm thấy")

    follow = await crud_saved_follow.follow_seller(db, current_user.id, seller_id)
    seller.follower_count = await crud_saved_follow.get_follower_count(db, seller_id)
    current_user.following_count = await crud_saved_follow.get_following_count(db, current_user.id)
    db.add(seller)
    db.add(current_user)
    await db.commit()

    return FollowedSellerItem(created_at=follow.created_at, seller=UserPublic.model_validate(seller))


@router.delete("/followed-sellers/{seller_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def unfollow_seller(
    seller_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: SessionDep,
):
    removed = await crud_saved_follow.unfollow_seller(db, current_user.id, seller_id)
    if not removed:
        raise HTTPException(
            status_code=404, detail="Bạn chưa theo dõi người bán này")

    seller = await crud_user.get_user_by_id(db, seller_id)
    if seller:
        seller.follower_count = await crud_saved_follow.get_follower_count(db, seller_id)
        db.add(seller)

    current_user.following_count = await crud_saved_follow.get_following_count(db, current_user.id)
    db.add(current_user)
    await db.commit()
    return None
