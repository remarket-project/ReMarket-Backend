# This file allows app/models to be imported as a package
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
from app.models.enums import (
    ConditionGrade,
    ListingStatus,
    NotificationType,
    OfferStatus,
    OrderStatus,
    UserRole,
    TransactionType,
    EscrowStatus,
)
from app.models.escrow import Escrow
from app.models.wallet import Wallet, WalletTransaction
from app.models.notification import Notification
from app.models.review import Review
from app.models.admin_audit import AdminAuditLog
from app.models.saved_follow import SavedListing, FollowSeller
from app.models.chat import ChatConversation, Message, ConversationParticipant
from app.models.order_event import OrderEvent
from app.models.order import Order
from app.models.offer import Offer
from app.models.static_content import StaticContent
from sqlmodel import SQLModel

from app.models.category import (
    Category,
    CategoriesPublic,
    CategoryCreate,
    CategoryPublic,
    CategoryUpdate,
)
from app.models.listing import (
    Listing,
    ListingImage,
)
# Backwards compatibility: some tests and older code reference `Item`
Item = Listing

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
    "Listing",
    "Item",
    "ListingImage",
    "Offer",
    "Order",
    "OrderEvent",
    "ChatConversation",
    "Message",
    "ConversationParticipant",
    "SavedListing",
    "FollowSeller",
    "AdminAuditLog",
    "StaticContent",
    "Review",
    "Notification",
    "Wallet",
    "WalletTransaction",
    "Escrow",
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
    "TransactionType",
    "EscrowStatus",
]
