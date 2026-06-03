# This file allows app/models to be imported as a package
from sqlmodel import SQLModel

from app.models.admin_audit import AdminAuditLog
from app.models.category import (
    CategoriesPublic,
    Category,
    CategoryCreate,
    CategoryPublic,
    CategoryUpdate,
)
from app.models.chat import ChatConversation, ConversationParticipant, Message as ChatMessage
from app.models.enums import (
    ConditionGrade,
    EscrowStatus,
    ListingStatus,
    NotificationType,
    OfferStatus,
    OrderStatus,
    TransactionType,
    UserRole,
)
from app.models.escrow import Escrow
from app.models.listing import (
    Listing,
    ListingImage,
)
from app.models.notification import Notification
from app.models.offer import Offer
from app.models.order import Order
from app.models.order_event import OrderEvent
from app.models.review import Review
from app.models.saved_follow import FollowSeller, SavedListing
from app.models.static_content import StaticContent
from app.models.user import (
    Message as UserMessage,
    NewPassword,
    Token,
    TokenPayload,
    UpdatePassword,
    User,
    UserCreate,
    UserPrivate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)
from app.models.wallet import Wallet, WalletTransaction

# Backwards compatibility: some tests and older code reference `Item`
Item = Listing

# Backwards compatibility: expose both Message types
Message = ChatMessage  # Default for most existing imports

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
    "ChatMessage",
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
    "UserMessage",
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
