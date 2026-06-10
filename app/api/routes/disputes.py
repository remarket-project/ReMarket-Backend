"""
Dispute API endpoints.

Allows buyers/sellers to create disputes with evidence.
"""
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.core.websocket_manager import ws_manager
from app.crud import crud_dispute, crud_notification, crud_order
from app.models.dispute import Dispute
from app.models.enums import NotificationType, OrderStatus
from app.schemas.dispute import DisputeCreate, DisputeRead

router = APIRouter(prefix="/disputes", tags=["Disputes"])


@router.post("", response_model=DisputeRead, status_code=status.HTTP_201_CREATED)
async def create_dispute(
    current_user: CurrentUser,
    db: SessionDep,
    data: DisputeCreate,
):
    """Create a dispute for an order (buyer or seller)."""
    order = await crud_order.get_order_by_id(db, data.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.buyer_id != current_user.id and order.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only buyer or seller can dispute")

    if order.status not in (OrderStatus.DELIVERED, OrderStatus.SHIPPING):
        raise HTTPException(status_code=400, detail=f"Cannot dispute order with status {order.status}")

    # Check existing open dispute
    existing = await crud_dispute.get_dispute_by_order(db, data.order_id)
    if existing and existing.status == "open":
        raise HTTPException(status_code=400, detail="An open dispute already exists for this order")

    dispute = await crud_dispute.create_dispute(
        db=db,
        order_id=data.order_id,
        raised_by=current_user.id,
        reason=data.reason,
    )

    # Upload evidence if provided
    if data.evidence_images:
        for image_url in data.evidence_images:
            await crud_dispute.add_evidence(
                db=db,
                dispute_id=dispute.id,
                uploaded_by=current_user.id,
                image_url=image_url,
            )

    # Re-fetch dispute with evidence loaded for response serialization
    result = await db.execute(
        select(Dispute)
        .options(selectinload(Dispute.evidence))
        .where(Dispute.id == dispute.id)
    )
    dispute = result.scalar_one()

    # Notify the other party
    target_id = order.seller_id if current_user.id == order.buyer_id else order.buyer_id
    await crud_notification.create_notification(
        db=db,
        user_id=target_id,
        type=NotificationType.DISPUTE_OPENED,
        title="Khiếu nại được mở",
        message=f"Có khiếu nại cho đơn hàng #{str(order.id)[:8]}.",
        data={"dispute_id": str(dispute.id), "order_id": str(order.id)},
    )

    # WS events
    await ws_manager.send_to_user(order.buyer_id, {
        "type": "order_status_updated",
        "order_id": str(order.id),
    })
    await ws_manager.send_to_user(order.seller_id, {
        "type": "order_status_updated",
        "order_id": str(order.id),
    })

    return dispute


@router.get("/order/{order_id}", response_model=DisputeRead | None)
async def get_dispute_by_order(
    current_user: CurrentUser,
    db: SessionDep,
    order_id: uuid.UUID,
):
    """Get dispute for an order."""
    order = await crud_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.buyer_id != current_user.id and order.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    dispute = await crud_dispute.get_dispute_by_order(db, order_id)
    return dispute


@router.get("/{dispute_id}", response_model=DisputeRead)
async def get_dispute(
    current_user: CurrentUser,
    db: SessionDep,
    dispute_id: uuid.UUID,
):
    """Get dispute detail."""
    dispute = await crud_dispute.get_dispute_by_id(db, dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    order = await crud_order.get_order_by_id(db, dispute.order_id)
    if order and order.buyer_id != current_user.id and order.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return dispute
