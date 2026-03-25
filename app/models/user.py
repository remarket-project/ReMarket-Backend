"""
User model for ReMarket.

Handles user accounts, profiles, and trust scores.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import EmailStr
from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel

from .enums import UserRole

if TYPE_CHECKING:
    from app.models.listing import Listing
    from app.models.offer import Offer
    from app.models.order import Order
    from app.models.review import Review


def get_datetime_utc() -> datetime:
    """Get current datetime in UTC."""
    return datetime.now(timezone.utc)


# ============================================================================
# Base Classes (Shared Properties)
# ============================================================================

class UserBase(SQLModel):
    """Shared user properties."""
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    full_name: str = Field(max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    avatar_url: str | None = None
    bio: str | None = None

    # Address fields
    province: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    ward: str | None = Field(default=None, max_length=100)
    address_detail: str | None = Field(default=None, max_length=255)

    # Verification
    is_phone_verified: bool = Field(default=False)
    is_email_verified: bool = Field(default=False)

    # Trust & Rating
    trust_score: Decimal = Field(default=Decimal(
        "0.0"), decimal_places=1, max_digits=5)
    rating_avg: Decimal = Field(default=Decimal(
        "0.00"), decimal_places=2, max_digits=3)
    rating_count: int = Field(default=0)
    completed_orders: int = Field(default=0)

    # Status
    role: UserRole = Field(default=UserRole.USER)
    is_active: bool = True


# ============================================================================
# Request Models (API Input)
# ============================================================================

class UserRegister(SQLModel):
    """Request body for user registration (sign up)."""
    email: EmailStr = Field(max_length=255)
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Password must be at least 8 characters"
    )
    phone: str | None = Field(default=None, max_length=20)


class UserCreate(UserBase):
    """Request body for user creation (admin)."""
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Password must be at least 8 characters"
    )


class UserUpdate(SQLModel):
    """Request body for updating user profile."""
    full_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    avatar_url: str | None = None
    bio: str | None = None
    province: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    ward: str | None = Field(default=None, max_length=100)
    address_detail: str | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    """Request body for changing password."""
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# ============================================================================
# Database Model
# ============================================================================

class User(UserBase, table=True):
    """User database model."""

    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    password_hash: str = Field(max_length=255)
    hashed_refresh_token: str | None = Field(default=None, max_length=255)

    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    # Relationships
    listings: list["Listing"] = Relationship(
        back_populates="seller", cascade_delete=True)
    offers_made: list["Offer"] = Relationship(
        back_populates="buyer", cascade_delete=True)
    orders_as_buyer: list["Order"] = Relationship(
        back_populates="buyer",
        cascade_delete=True,
        sa_relationship_kwargs={"foreign_keys": "Order.buyer_id"}
    )
    orders_as_seller: list["Order"] = Relationship(
        back_populates="seller",
        cascade_delete=True,
        sa_relationship_kwargs={"foreign_keys": "Order.seller_id"}
    )
    reviews_given: list["Review"] = Relationship(
        back_populates="reviewer",
        cascade_delete=True,
        sa_relationship_kwargs={"foreign_keys": "Review.reviewer_id"}
    )
    reviews_received: list["Review"] = Relationship(
        back_populates="reviewee",
        cascade_delete=True,
        sa_relationship_kwargs={"foreign_keys": "Review.reviewee_id"}
    )


# ============================================================================
# Legacy Models (To be refactored)
# ============================================================================

class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class Message(SQLModel):
    message: str


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


# ============================================================================
# Response Models (API Output)
# ============================================================================

class UserPublic(SQLModel):
    """Public user profile (minimal info for other users)."""
    id: uuid.UUID
    full_name: str
    avatar_url: str | None = None
    bio: str | None = None
    trust_score: Decimal
    rating_avg: Decimal
    rating_count: int
    completed_orders: int
    created_at: datetime


class UserPrivate(UserBase):
    """Private user profile (full info for authenticated user)."""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class UsersPublic(SQLModel):
    """Response body for listing users."""
    data: list[UserPublic]
    count: int


# ============================================================================
# JWT Token Models
# ============================================================================

class TokenPayload(SQLModel):
    """JWT token payload."""
    sub: str  # subject = user_id
    role: UserRole
