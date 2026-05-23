"""
Escrow API endpoints.

Handles escrow accounts, funding, releases, and disputes.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, SessionDep, CurrentAdmin
from app.crud import crud_escrow, crud_wallet, crud_order
from app.models.enums import EscrowStatus, TransactionType, UserRole, OrderStatus
from app.schemas.escrow import EscrowRead, OpenDisputeRequest
from app.core.websocket_manager import ws_manager
from app.crud.crud_notification import create_notification
from app.models.enums import NotificationType

router = APIRouter(prefix="/escrows", tags=["Escrow"])


# ============================================================================
# Get Escrow by Order ID
# ============================================================================

@router.get("/{order_id:uuid}", response_model=EscrowRead)
async def get_escrow(
    order_id: uuid.UUID,
    current_user: CurrentUser,
    db: SessionDep
) -> EscrowRead:
    """
    Get escrow details for an order.

    **Path parameters:**
    - order_id: Order UUID

    **Response:**
    - Escrow details

    **Errors:**
    - 404: Escrow not found
    - 403: Not buyer or seller of order
    """
    escrow = await crud_escrow.get_escrow_by_order_id(db, order_id)
    if not escrow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escrow not found"
        )

    # Check authorization (buyer or seller)
    order = await crud_order.get_order_by_id(db, order_id)
    if not order or (order.buyer_id != current_user.id and order.seller_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this escrow"
        )

    return escrow


# ============================================================================
# Fund Escrow
# ============================================================================

@router.post("/{order_id:uuid}/fund", response_model=EscrowRead)
async def fund_escrow(
    order_id: uuid.UUID,
    current_user: CurrentUser,
    db: SessionDep
) -> EscrowRead:
    """
    Fund escrow account (buyer pays).

    Locks funds in buyer's wallet and updates escrow status.

    **Path parameters:**
    - order_id: Order UUID

    **Response:**
    - Updated escrow

    **Errors:**
    - 400: Invalid escrow status or insufficient funds
    - 403: Not buyer of order
    - 404: Order or escrow not found
    """
    # Get order and verify buyer
    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    if order.buyer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only buyer can fund escrow"
        )

    # Get escrow
    escrow = await crud_escrow.get_escrow_by_order_id(db, order_id)
    if not escrow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escrow not found"
        )

    if escrow.status != EscrowStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot fund escrow with status: {escrow.status}"
        )

    # Get or create buyer wallet
    buyer_wallet = await crud_wallet.get_or_create_wallet(db, current_user.id)

    # Lock funds in wallet
    try:
        updated_wallet, transaction = await crud_wallet.lock_balance(
            db=db,
            wallet_id=buyer_wallet.id,
            amount=escrow.amount,
            order_id=order_id,
            description=f"Escrow for order {order_id}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Update escrow status
    updated_escrow = await crud_escrow.fund_escrow(db, escrow.id)

    # Send notification to seller
    seller_notification = await create_notification(
        db=db,
        user_id=order.seller_id,
        type=NotificationType.ORDER_CONFIRMED.value,
        title="Đơn hàng được thanh toán",
        description=f"Buyer đã nạp tiền escrow cho đơn hàng #{order_id}",
        related_id=str(order_id)
    )
    await ws_manager.send_to_user(
        order.seller_id,
        {
            "type": "notification",
            "data": {
                "id": str(seller_notification.id),
                "type": str(seller_notification.type),
                "title": seller_notification.title,
                "message": seller_notification.message,
                "data": seller_notification.data or {}
            }
        }
    )

    return updated_escrow


# ============================================================================
# Request Refund (Escalates to Dispute)
# ============================================================================

@router.post("/{order_id:uuid}/refund-request", response_model=EscrowRead)
async def request_refund(
    order_id: uuid.UUID,
    current_user: CurrentUser,
    db: SessionDep,
    data: OpenDisputeRequest
) -> EscrowRead:
    """
    Request a refund by opening escrow dispute.

    This keeps dispute handling centralized through admin resolution.
    """
    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    if order.buyer_id != current_user.id and order.seller_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only buyer or seller can request refund"
        )

    escrow = await crud_escrow.get_escrow_by_order_id(db, order_id)
    if not escrow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escrow not found"
        )

    if escrow.status not in {
        EscrowStatus.FUNDED.value,
        EscrowStatus.RELEASE_REQUESTED.value,
        EscrowStatus.DISPUTED.value,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot request refund with escrow status: {escrow.status}"
        )

    reason = f"[Refund Request] {data.reason}"
    updated_escrow = await crud_escrow.open_dispute(db, escrow.id, reason)

    from app.crud.crud_user import get_users_list
    admins = await get_users_list(db, limit=1000)
    admin_ids = [str(a.id)
                 for a in admins if hasattr(a, "role") and a.role == UserRole.ADMIN]

    for admin_id in admin_ids:
        notification = await create_notification(
            db=db,
            user_id=uuid.UUID(admin_id),
            type=NotificationType.ORDER_CANCELLED.value,
            title="Yêu cầu hoàn tiền escrow",
            description=f"Đơn hàng #{order_id} có yêu cầu hoàn tiền. Lý do: {data.reason[:50]}...",
            related_id=str(order_id)
        )
        await ws_manager.send_to_user(
            uuid.UUID(admin_id),
            {
                "type": "notification",
                "data": {
                    "id": str(notification.id),
                    "type": str(notification.type),
                    "title": notification.title,
                    "message": notification.message,
                    "data": notification.data or {}
                },
            },
        )

    return updated_escrow


# ============================================================================
# Request Release (Buyer received goods)
# ============================================================================

@router.post("/{order_id:uuid}/release-request", response_model=EscrowRead)
async def request_release(
    order_id: uuid.UUID,
    current_user: CurrentUser,
    db: SessionDep
) -> EscrowRead:
    """
    Request escrow release (buyer confirms receipt).

    **Path parameters:**
    - order_id: Order UUID

    **Response:**
    - Updated escrow

    **Errors:**
    - 400: Invalid escrow status
    - 403: Not buyer of order
    - 404: Order or escrow not found
    """
    # Get order and verify buyer
    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    if order.buyer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only buyer can request release"
        )

    # Get escrow
    escrow = await crud_escrow.get_escrow_by_order_id(db, order_id)
    if not escrow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escrow not found"
        )

    try:
        updated_escrow = await crud_escrow.request_release(db, escrow.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Send notification to seller
    seller_notification = await create_notification(
        db=db,
        user_id=order.seller_id,
        type=NotificationType.ORDER_DELIVERED.value,
        title="Yêu cầu thanh toán",
        description=f"Buyer xác nhận đã nhận hàng, yêu cầu giải phóng escrow",
        related_id=str(order_id)
    )
    await ws_manager.send_to_user(
        order.seller_id,
        {
            "type": "notification",
            "data": {
                "id": str(seller_notification.id),
                "type": str(seller_notification.type),
                "title": seller_notification.title,
                "message": seller_notification.message,
                "data": seller_notification.data or {}
            }
        }
    )

    return updated_escrow


# ============================================================================
# Confirm Release (Seller receives payment)
# ============================================================================

@router.post("/{order_id:uuid}/confirm-release", response_model=EscrowRead)
async def confirm_release(
    order_id: uuid.UUID,
    current_user: CurrentUser,
    db: SessionDep
) -> EscrowRead:
    """
    Confirm escrow release (seller accepts payment).

    Transfers locked funds from buyer to seller.

    **Path parameters:**
    - order_id: Order UUID

    **Response:**
    - Updated escrow

    **Errors:**
    - 400: Invalid escrow status
    - 403: Not seller of order
    - 404: Order or escrow not found
    """
    # Get order and verify seller
    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    if order.seller_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only seller can confirm release"
        )

    # Get escrow
    escrow = await crud_escrow.get_escrow_by_order_id(db, order_id)
    if not escrow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escrow not found"
        )

    # Transfer locked funds from buyer to seller
    try:
        buyer_wallet, seller_wallet, buyer_tx, seller_tx = await crud_wallet.transfer_locked_to_user(
            db=db,
            from_wallet_id=escrow.buyer_wallet_id,
            to_wallet_id=escrow.seller_wallet_id,
            amount=escrow.amount,
            order_id=order_id,
            description=f"Payment for order {order_id}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Update escrow status
    updated_escrow = await crud_escrow.confirm_release(db, escrow.id)

    # Update order status to COMPLETED
    from app.crud.crud_order import update_order_status
    await update_order_status(db, order_id, OrderStatus.COMPLETED)

    # Send notifications
    buyer_notification = await create_notification(
        db=db,
        user_id=order.buyer_id,
        type=NotificationType.ORDER_COMPLETED.value,
        title="Đơn hàng hoàn thành",
        description=f"Thanh toán đã được giải phóng. Đơn hàng hoàn thành.",
        related_id=str(order_id)
    )
    await ws_manager.send_to_user(
        order.buyer_id,
        {
            "type": "notification",
            "data": {
                "id": str(buyer_notification.id),
                "type": str(buyer_notification.type),
                "title": buyer_notification.title,
                "message": buyer_notification.message,
                "data": buyer_notification.data or {}
            }
        }
    )

    seller_notification = await create_notification(
        db=db,
        user_id=order.seller_id,
        type=NotificationType.ORDER_COMPLETED.value,
        title="Thanh toán nhận được",
        description=f"Thanh toán escrow đã được giải phóng vào ví của bạn",
        related_id=str(order_id)
    )
    await ws_manager.send_to_user(
        order.seller_id,
        {
            "type": "notification",
            "data": {
                "id": str(seller_notification.id),
                "type": str(seller_notification.type),
                "title": seller_notification.title,
                "message": seller_notification.message,
                "data": seller_notification.data or {}
            }
        }
    )

    return updated_escrow


# ============================================================================
# Open Dispute
# ============================================================================

@router.post("/{order_id:uuid}/open-dispute", response_model=EscrowRead)
async def open_dispute(
    order_id: uuid.UUID,
    current_user: CurrentUser,
    db: SessionDep,
    data: OpenDisputeRequest
) -> EscrowRead:
    """
    Open a dispute on escrow.

    **Path parameters:**
    - order_id: Order UUID

    **Request body:**
    - reason: Reason for dispute (min 10 chars)

    **Response:**
    - Updated escrow

    **Errors:**
    - 400: Invalid escrow status
    - 403: Not buyer or seller of order
    - 404: Order or escrow not found
    """
    # Get order and verify buyer or seller
    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    if order.buyer_id != current_user.id and order.seller_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only buyer or seller can open dispute"
        )

    # Get escrow
    escrow = await crud_escrow.get_escrow_by_order_id(db, order_id)
    if not escrow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escrow not found"
        )

    # Open dispute
    updated_escrow = await crud_escrow.open_dispute(db, escrow.id, data.reason)

    # Notify admins
    from app.crud.crud_user import get_users_list
    admins = await get_users_list(db, limit=1000)
    admin_ids = [str(a.id)
                 for a in admins if hasattr(a, 'role') and a.role == UserRole.ADMIN]

    for admin_id in admin_ids:
        notification = await create_notification(
            db=db,
            user_id=uuid.UUID(admin_id),
            type=NotificationType.ORDER_CANCELLED.value,
            title="Tranh chấp escrow mới",
            description=f"Có tranh chấp về đơn hàng #{order_id}. Lý do: {data.reason[:50]}...",
            related_id=str(order_id)
        )
        await ws_manager.send_to_user(
            uuid.UUID(admin_id),
            {
                "type": "notification",
                "data": {
                    "id": str(notification.id),
                    "type": str(notification.type),
                    "title": notification.title,
                    "message": notification.message,
                    "data": notification.data or {}
                }
            }
        )

    return updated_escrow


# ============================================================================
# Get Disputed Escrows (Admin)
# ============================================================================

@router.get("/disputed", response_model=dict)
async def get_disputed_escrows(
    current_admin: CurrentAdmin,
    db: SessionDep,
    skip: int = 0,
    limit: int = 20
) -> dict:
    """
    Get list of disputed escrows (admin only).

    **Query parameters:**
    - skip: Number of records to skip (default: 0)
    - limit: Maximum records to return (default: 20)

    **Response:**
    - List of disputed escrows and total count

    **Errors:**
    - 401: Unauthorized
    - 403: Not admin
    """
    if limit > 100:
        limit = 100

    escrows, total = await crud_escrow.get_disputed_escrows(db, skip=skip, limit=limit)

    return {
        "escrows": escrows,
        "total": total
    }
