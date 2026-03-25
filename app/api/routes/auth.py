"""
Auth API endpoints.

Handles user registration, login, token refresh, and logout.
"""
from datetime import timedelta
from typing import Any, Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, SessionDep, TokenDep
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    hash_token,
    verify_token_hash,
    verify_password,
)
from app.crud import crud_user
from app.models import User, UserRole, TokenPayload
from app.schemas.auth import RefreshTokenRequest, TokenResponse, MessageResponse
from app.models import UserRegister

import jwt
from jwt.exceptions import InvalidTokenError

router = APIRouter(prefix="/auth", tags=["auth"])


# ============================================================================
# Register
# ============================================================================

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    summary="Register a new user",
    description="Create a new user account and return JWT tokens."
)
async def register(data: UserRegister, session: SessionDep) -> TokenResponse:
    """
    Register a new user account.

    **Request body:**
    - email: User email (must be unique)
    - full_name: User's full name
    - password: Password (min 8 chars)
    - phone: (optional) Phone number

    **Response:**
    - access_token: JWT token for API requests
    - refresh_token: Token for refreshing access token
    - user: User profile info
    """
    # Check if email already exists
    existing_user = await crud_user.get_user_by_email(session, data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    # Create new user
    user = await crud_user.create_user(session, data)

    # Generate tokens
    access_token_expires = timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(subject=str(user.id))

    # Store hashed refresh token
    await crud_user.update_user_refresh_token(session, user.id, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user
    )


# ============================================================================
# Login
# ============================================================================

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User login",
    description="Authenticate user and return JWT tokens. Compatible with OAuth2 password flow."
)
async def login(session: SessionDep, credentials: Annotated[OAuth2PasswordRequestForm, Depends()]) -> TokenResponse:
    """
    User login with email and password.

    **Request body:**
    - email: User email
    - password: User password

    **Response:**
    - access_token: JWT token for API requests
    - refresh_token: Token for refreshing access token
    - user: User profile info

    **Errors:**
    - 401: Invalid email or password
    - 400: User account inactive
    """
    # Find user by email
    user = await crud_user.get_user_by_email(session, credentials.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive"
        )

    # Verify password
    is_valid = verify_password(credentials.password, user.password_hash)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Generate tokens
    access_token_expires = timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(subject=str(user.id))

    # Store hashed refresh token
    await crud_user.update_user_refresh_token(session, user.id, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user
    )


# ============================================================================
# Refresh Token
# ============================================================================

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Get a new access token using a refresh token."
)
async def refresh_access_token(
    req: RefreshTokenRequest,
    session: SessionDep
) -> TokenResponse:
    """
    Refresh JWT access token with refresh token.

    Implements token rotation: old refresh token is revoked, new one issued.

    **Request body:**
    - refresh_token: Current refresh token

    **Response:**
    - access_token: New JWT token
    - refresh_token: New refresh token (old one invalidated)
    - user: Updated user profile

    **Errors:**
    - 401: Invalid or expired refresh token
    """
    # Decode and verify refresh token JWT
    try:
        payload = jwt.decode(
            req.refresh_token,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )
        # Verify token type
        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type")
        user_id = uuid.UUID(payload.get("sub", ""))
    except (InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Get user and verify refresh token hash
    user = await crud_user.get_user_by_id(session, user_id)
    if not user or not user.hashed_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Verify token hash matches
    if not verify_token_hash(req.refresh_token, user.hashed_refresh_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Generate new tokens (token rotation)
    access_token_expires = timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=access_token_expires
    )
    new_refresh_token = create_refresh_token(subject=str(user.id))

    # Update refresh token (invalidate old one)
    await crud_user.update_user_refresh_token(session, user.id, new_refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user=user
    )


# ============================================================================
# Logout
# ============================================================================

@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="User logout",
    description="Invalidate refresh token (revoke session)."
)
async def logout(
    current_user: CurrentUser,
    session: SessionDep
) -> dict[str, Any]:
    """
    Logout current user.

    Invalidates refresh token, forcing user to login again.

    **Response:**
    - 200 OK on success

    **Errors:**
    - 401: Unauthorized (not logged in)
    """
    # Revoke refresh token
    await crud_user.update_user_refresh_token(session, current_user.id, None)

    return {"message": "Successfully logged out"}
