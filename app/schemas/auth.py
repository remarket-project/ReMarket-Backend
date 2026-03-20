"""
Auth schemas for API endpoints.

Handles login, registration, token refresh requests/responses.
"""
from pydantic import EmailStr, Field
from sqlmodel import SQLModel

from app.models import UserPrivate


class LoginRequest(SQLModel):
    """Request body for login endpoint."""
    email: EmailStr = Field(description="User email")
    password: str = Field(min_length=8, max_length=128,
                          description="User password")


class RefreshTokenRequest(SQLModel):
    """Request body for token refresh endpoint."""
    refresh_token: str = Field(description="Refresh token")


class TokenResponse(SQLModel):
    """Response body containing JWT tokens and user info."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPrivate


class MessageResponse(SQLModel):
    """Generic response with a message."""
    message: str
