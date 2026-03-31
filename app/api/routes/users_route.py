"""
User API endpoints.

Handles user profile management and public user info access.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, SessionDep, CurrentAdmin
from app.core.security import (
    verify_password,
    get_password_hash,
)
from app.crud import crud_user
from app.models import User, UserUpdate, UserPrivate, UserPublic, UsersPublic
from app.schemas.user import UserUpdate as UserUpdateSchema
from app.schemas.auth import ChangePasswordRequest, MessageResponse

router = APIRouter(prefix="/users", tags=["users"])


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
    users = await crud_user.get_users(session, skip=skip, limit=limit)
    count = await crud_user.get_users_count(session)

    return UsersPublic(data=users, count=count)
