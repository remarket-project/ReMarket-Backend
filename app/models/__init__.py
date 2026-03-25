# This file allows app/models to be imported as a package
from sqlmodel import SQLModel

from app.models.category import (
    Category,
    CategoriesPublic,
    CategoryCreate,
    CategoryPublic,
    CategoryUpdate,
    CategoryWithChildren,
)
from app.models.listing import (
    Listing,
    ListingImage,
)
from app.models.offer import Offer
from app.models.order import Order
from app.models.review import Review
from app.models.notification import Notification
from app.models.enums import (
    ConditionGrade,
    ListingStatus,
    NotificationType,
    OfferStatus,
    OrderStatus,
    UserRole,
)
from app.models.user import (
    User,
    UserCreate,
    UserPrivate,
    UserPublic,
    UserRegister,
    UserUpdate,
    UsersPublic,
    UpdatePassword,
    TokenPayload,
    UserUpdateMe,
    Message,
    Token,
    NewPassword,
)

__all__ = [
    # Core
    "SQLModel",
    # Models
    "User",
    "Category",
    "CategoriesPublic",
    "CategoryCreate",
    "CategoryPublic",
    "CategoryUpdate",
    "CategoryWithChildren",
    "Listing",
    "ListingImage",
    "Offer",
    "Order",
    "Review",
    "Notification",
    # Schemas
    "UserCreate",
    "UserRegister",
    "UserUpdate",
    "UserPublic",
    "UserPrivate",
    "UsersPublic",
    "UpdatePassword",
    "TokenPayload",
    "UserUpdateMe",
    "Message",
    "Token",
    "NewPassword",
    # Enums
    "UserRole",
    "ListingStatus",
    "ConditionGrade",
    "OfferStatus",
    "OrderStatus",
    "NotificationType",
]
