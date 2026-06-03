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
    OFFER_COUNTERED = "offer_countered"
    OFFER_EXPIRED = "offer_expired"
    ORDER_CREATED = "order_created"
    ORDER_CONFIRMED = "order_confirmed"
    ORDER_SHIPPING = "order_shipping"
    ORDER_DELIVERED = "order_delivered"
    ORDER_COMPLETED = "order_completed"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_STATUS_UPDATED = "order_status_updated"
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
    PENDING = "pending"                    # Chờ buyer fund
    FUNDED = "funded"                      # Đã fund, chờ giao hàng
    RELEASE_REQUESTED = "release_requested"  # Buyer request release
    RELEASED = "released"                  # Đã release cho seller
    DISPUTED = "disputed"                  # Tranh chấp
    REFUNDED = "refunded"                  # Hoàn tiền cho buyer
