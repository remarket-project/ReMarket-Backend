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


class PaymentMethod(str, Enum):
    """Phương thức thanh toán."""
    WALLET = "wallet"  # Thanh toán từ ví (escrow)
    COD = "cod"        # Thanh toán khi nhận hàng


class OrderStatus(str, Enum):
    """Status of an order."""
    PENDING = "pending"            # Vừa tạo, chờ admin xử lý
    SHIPPING = "shipping"          # Admin đang vận chuyển
    DELIVERED = "delivered"        # Admin đã giao hàng
    DELIVERY_FAILED = "delivery_failed"  # Giao hàng thất bại
    RETURNING = "returning"        # Đang hoàn trả
    RETURNED = "returned"          # Đã hoàn trả (terminal)
    COMPLETED = "completed"        # Hoàn tất (terminal)
    CANCELLED = "cancelled"        # Hủy (terminal)
    DISPUTED = "disputed"          # Đang tranh chấp


class NotificationType(str, Enum):
    """Type of notification."""
    LISTING_APPROVED = "listing_approved"
    LISTING_REJECTED = "listing_rejected"
    OFFER_RECEIVED = "offer_received"
    OFFER_ACCEPTED = "offer_accepted"
    OFFER_REJECTED = "offer_rejected"
    OFFER_COUNTERED = "offer_countered"
    OFFER_EXPIRED = "offer_expired"
    ORDER_CREATED = "order_created"
    ORDER_SHIPPING = "order_shipping"
    ORDER_DELIVERED = "order_delivered"
    ORDER_COMPLETED = "order_completed"
    ORDER_ACCEPTED = "order_accepted"
    ORDER_AUTO_COMPLETED = "order_auto_completed"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_STATUS_UPDATED = "order_status_updated"
    DISPUTE_OPENED = "dispute_opened"
    DISPUTE_RESOLVED = "dispute_resolved"
    SHIPPING_CREATED = "shipping_created"
    SHIPPING_DELIVERED = "shipping_delivered"
    RETURN_REQUESTED = "return_requested"
    RETURN_CONFIRMED = "return_confirmed"
    REVIEW_RECEIVED = "review_received"
    WALLET_BALANCE_UPDATED = "wallet_balance_updated"
    WALLET_LOCKED = "wallet_locked"
    WALLET_RELEASED = "wallet_released"


class TransactionType(str, Enum):
    """Type of wallet transaction."""
    DEPOSIT = "deposit"                    # Nạp tiền
    DEPOSIT_PENDING = "deposit_pending"    # Đang chờ xử lý nạp
    WITHDRAW = "withdraw"                  # Rút tiền
    WITHDRAW_PENDING = "withdraw_pending"  # Đang chờ xử lý rút
    WITHDRAW_COMPLETED = "withdraw_completed"  # Rút thành công
    WITHDRAW_FAILED = "withdraw_failed"    # Rút thất bại
    ESCROW_LOCK = "escrow_lock"           # Khóa tiền vào escrow
    ESCROW_RELEASE = "escrow_release"     # Giải phóng từ escrow
    ESCROW_REFUND = "escrow_refund"       # Hoàn tiền từ escrow
    PAYMENT = "payment"                    # Thanh toán


class EscrowStatus(str, Enum):
    """Status of escrow account."""
    PENDING = "pending"            # Chờ fund
    FUNDED = "funded"              # Đã fund
    RELEASED = "released"          # Đã giải ngân cho seller
    REFUNDED = "refunded"          # Hoàn tiền cho buyer
    DISPUTED = "disputed"          # Đang tranh chấp
