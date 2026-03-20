"""
Enums for ReMarket models.

Contains all enum types used throughout the application.
"""
from enum import Enum


class UserRole(str, Enum):
    """User roles in the system."""
    USER = "user"
    ADMIN = "admin"


class ListingStatus(str, Enum):
    """Status of a listing."""
    PENDING = "pending"        # Chờ admin duyệt
    ACTIVE = "active"          # Được duyệt, công khai
    SOLD = "sold"              # Đã bán
    HIDDEN = "hidden"          # Bị ẩn (vi phạm hoặc seller ẩn)
    REJECTED = "rejected"      # Bị từ chối duyệt


class ConditionGrade(str, Enum):
    """Condition grade of a product."""
    BRAND_NEW = "brand_new"    # Mới chưa dùng
    LIKE_NEW = "like_new"      # Như mới
    GOOD = "good"              # Tốt
    FAIR = "fair"              # Bình thường
    POOR = "poor"              # Kém


class OfferStatus(str, Enum):
    """Status of an offer (negotiation)."""
    PENDING = "pending"        # Chờ phản hồi
    ACCEPTED = "accepted"      # Chấp nhận → Auto tạo order
    REJECTED = "rejected"      # Từ chối
    COUNTERED = "countered"    # Đưa ra giá mới
    EXPIRED = "expired"        # Hết hạn


class OrderStatus(str, Enum):
    """Status of an order."""
    PENDING = "pending"        # Vừa tạo, chờ xác nhận
    CONFIRMED = "confirmed"    # Đã xác nhận
    SHIPPING = "shipping"      # Đang vận chuyển
    DELIVERED = "delivered"    # Đã giao hàng
    COMPLETED = "completed"    # Hoàn tất (có thể review)
    CANCELLED = "cancelled"    # Hủy


class NotificationType(str, Enum):
    """Type of notification."""
    LISTING_APPROVED = "listing_approved"
    LISTING_REJECTED = "listing_rejected"
    OFFER_RECEIVED = "offer_received"
    OFFER_ACCEPTED = "offer_accepted"
    OFFER_REJECTED = "offer_rejected"
    ORDER_CREATED = "order_created"
    ORDER_COMPLETED = "order_completed"
    REVIEW_RECEIVED = "review_received"
