"""
User API endpoints.

Handles user profile management and public user info access.
"""
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import case, func, select

from app.api.deps import CurrentAdmin, CurrentUser, SessionDep
from app.core.security import (
    get_password_hash,
    verify_password,
)
from app.crud import crud_listing, crud_user
from app.models import UserPrivate, UserPublic, UsersPublic
from app.models.enums import ListingStatus
from app.models.listing import Listing
from app.models.review import Review
from app.schemas.auth import ChangePasswordRequest, MessageResponse
from app.schemas.listing import ListingWithImages
from app.schemas.user import UserUpdate as UserUpdateSchema

router = APIRouter(prefix="/users", tags=["users"])


class ReviewSummaryRead(BaseModel):
    average_rating: Decimal
    total_reviews: int
    rating_breakdown: dict[str, int]


class SellerShopProfileRead(BaseModel):
    seller: UserPublic
    total_active_listings: int
    recent_listings: list[ListingWithImages]
    review_summary: ReviewSummaryRead


class ReviewSummaryOnlyRead(BaseModel):
    user_id: uuid.UUID
    average_rating: Decimal
    total_reviews: int
    rating_breakdown: dict[str, int]


async def _build_listing_with_images(session: SessionDep, listing: Listing) -> ListingWithImages:
    images = await crud_listing.get_listing_images(session, str(listing.id))
    listing_dict = listing.model_dump()
    listing_dict["images"] = images
    return ListingWithImages(**listing_dict)


async def _get_review_summary(session: SessionDep, user_id: uuid.UUID) -> ReviewSummaryRead:
    result = await session.execute(
        select(
            func.count(Review.id),
            func.avg(Review.rating),
            func.sum(case((Review.rating == 5, 1), else_=0)),
            func.sum(case((Review.rating == 4, 1), else_=0)),
            func.sum(case((Review.rating == 3, 1), else_=0)),
            func.sum(case((Review.rating == 2, 1), else_=0)),
            func.sum(case((Review.rating == 1, 1), else_=0)),
        ).where(Review.reviewee_id == user_id)
    )
    total_reviews, avg_rating, five, four, three, two, one = result.one()
    return ReviewSummaryRead(
        average_rating=Decimal(str(round(float(avg_rating or 0), 2))),
        total_reviews=int(total_reviews or 0),
        rating_breakdown={
            "5": int(five or 0),
            "4": int(four or 0),
            "3": int(three or 0),
            "2": int(two or 0),
            "1": int(one or 0),
        },
    )


# ============================================================================
# Get Current User Profile
# ============================================================================

@router.get(
    "/me",
    response_model=UserPrivate,
    summary="Get my profile",
    description="Get the current authenticated user's full profile."
)
async def get_current_user_info(current_user: CurrentUser) -> UserPrivate:
    """
    Get current user's full profile.

    **Response:**
    - User's private information including email, phone, address, etc.

    **Errors:**
    - 401: Unauthorized (not logged in)
    """
    return current_user


# ============================================================================
# Update Current User Profile
# ============================================================================

@router.put(
    "/me",
    response_model=UserPrivate,
    summary="Update my profile",
    description="Update the current user's profile information."
)
async def update_my_profile(
    data: UserUpdateSchema,
    current_user: CurrentUser,
    session: SessionDep
) -> UserPrivate:
    """
    Update current user's profile.

    **Request body:**
    - full_name: (optional) Full name
    - phone: (optional) Phone number
    - avatar_url: (optional) Avatar image URL
    - bio: (optional) Bio/description
    - province/district/ward/address_detail: (optional) Address fields

    **Response:**
    - Updated user profile

    **Errors:**
    - 401: Unauthorized
    """
    updated_user = await crud_user.update_user(session, current_user.id, data)
    return updated_user


# ============================================================================
# Change Password
# ============================================================================

@router.put(
    "/me/password",
    response_model=MessageResponse,
    summary="Change password",
    description="Change the current user's password."
)
async def change_password(
    data: ChangePasswordRequest,
    current_user: CurrentUser,
    session: SessionDep
) -> MessageResponse:
    """
    Change current user's password.

    **Request body:**
    - current_password: Current password for verification
    - new_password: New password (min 8 characters)
    - confirm_password: Confirm new password (must match new_password)

    **Response:**
    - Success message

    **Errors:**
    - 400: Current password incorrect or new passwords don't match
    - 401: Unauthorized
    """
    # Verify passwords match
    if data.new_password != data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New passwords do not match"
        )

    # Verify current password
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Update password
    user = await crud_user.get_user_by_id(session, current_user.id)
    user.password_hash = get_password_hash(data.new_password)
    session.add(user)
    await session.commit()

    return MessageResponse(message="Password changed successfully")


# ============================================================================
# Get Public User Profile
# ============================================================================

@router.get(
    "/{user_id}",
    response_model=UserPublic,
    summary="Get user public profile",
    description="Get a user's public profile (minimal information)."
)
async def get_user_profile(
    user_id: uuid.UUID,
    session: SessionDep
) -> UserPublic:
    """
    Get public profile of a specific user.

    **Path parameters:**
    - user_id: UUID of the user

    **Response:**
    - User's public profile (no email, password, etc.)

    **Errors:**
    - 404: User not found
    """
    user = await crud_user.get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

    @router.get(
        "/{user_id}/reviews/summary",
        response_model=ReviewSummaryOnlyRead,
        summary="Get review summary",
        description="Get aggregate review stats for a user.",
    )
    async def get_user_review_summary(
        user_id: uuid.UUID,
        session: SessionDep,
    ) -> ReviewSummaryOnlyRead:
        user = await crud_user.get_user_by_id(session, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        summary = await _get_review_summary(session, user_id)
        return ReviewSummaryOnlyRead(
            user_id=user_id,
            average_rating=summary.average_rating,
            total_reviews=summary.total_reviews,
            rating_breakdown=summary.rating_breakdown,
        )

    @router.get(
        "/{user_id}/shop",
        response_model=SellerShopProfileRead,
        summary="Get seller shop profile",
        description="Get a seller profile with recent active listings and review stats.",
    )
    async def get_seller_shop_profile(
        user_id: uuid.UUID,
        session: SessionDep,
    ) -> SellerShopProfileRead:
        user = await crud_user.get_user_by_id(session, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        seller = UserPublic.model_validate(user)
        review_summary = await _get_review_summary(session, user_id)

        recent_listings_result, _ = await crud_listing.search_listings(
            session,
            seller_id=str(user_id),
            status=ListingStatus.ACTIVE,
            sort_by="newest",
            skip=0,
            limit=6,
        )
        recent_listings = [
            await _build_listing_with_images(session, listing)
            for listing in recent_listings_result
        ]

        total_active_listings_result = await session.execute(
            select(func.count()).select_from(Listing).where(
                Listing.seller_id == user_id,
                Listing.status == ListingStatus.ACTIVE,
            )
        )

        return SellerShopProfileRead(
            seller=seller,
            total_active_listings=int(
                total_active_listings_result.scalar_one()),
            recent_listings=recent_listings,
            review_summary=review_summary,
        )


# ============================================================================
# List Users (Admin Only)
# ============================================================================

@router.get(
    "/",
    response_model=UsersPublic,
    summary="List users",
    description="Get list of all users (admin only)."
)
async def list_users(
    session: SessionDep,
    current_admin: CurrentAdmin,
    skip: int = 0,
    limit: int = 100
) -> UsersPublic:
    """
    List all users with pagination (admin only).

    **Query parameters:**
    - skip: Number of users to skip (default: 0)
    - limit: Maximum users to return (default: 100)

    **Response:**
    - List of users and total count

    **Errors:**
    - 401: Unauthorized
    - 403: Not admin
    """
    users = await crud_user.get_users_list(session, skip=skip, limit=limit)
    count = await crud_user.get_users_count(session)

    return UsersPublic(data=users, count=count)
