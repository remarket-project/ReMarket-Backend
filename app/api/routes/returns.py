"""Return/refund request endpoints."""
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.crud import crud_order, crud_order_event
from app.crud.crud_return import get_return_by_id
from app.crud.crud_wallet import get_wallet_by_user_id, unlock_balance
from app.models.enums import OrderStatus
from app.models.return_request import ReturnReason, ReturnRequest, ReturnStatus


router = APIRouter(prefix="/returns", tags=["Returns"])


class ReturnRequestCreate(BaseModel):
    order_id: str
    reason: ReturnReason
    description: str | None = None
    images: list[str] = []


class ReturnRespond(BaseModel):
    approve: bool
    message: str | None = None


class ReturnShipInput(BaseModel):
    return_tracking_number: str
    return_carrier: str | None = None


@router.post("/request")
async def create_return_request(
    current_user: CurrentUser,
    db: SessionDep,
    data: ReturnRequestCreate,
):
    """Buyer gửi yêu cầu hoàn hàng (chỉ wallet, trong 7 ngày)."""
    try:
        order_uuid = uuid.UUID(data.order_id)
    except ValueError:
        raise HTTPException(422, "order_id không hợp lệ") from None
    order = await crud_order.get_order_by_id(db, order_uuid)
    if not order:
        raise HTTPException(404, "Order not found")
    if order.buyer_id != current_user.id:
        raise HTTPException(403, "Only buyer can request return")
    if order.payment_method != "wallet":
        raise HTTPException(400, "Only wallet orders can be returned")
    if order.status != OrderStatus.DELIVERED:
        raise HTTPException(400, "Order must be delivered to request return")
    if order.delivered_at:
        days_since = (datetime.now(timezone.utc) - order.delivered_at).days
        if days_since > 7:
            raise HTTPException(400, "Return period (7 days) has expired")

    from app.crud.crud_return import get_return_by_order_id
    existing = await get_return_by_order_id(db, order.id)
    if existing:
        raise HTTPException(400, "Return request already exists for this order")

    return_req = ReturnRequest(
        order_id=order.id,
        buyer_id=current_user.id,
        seller_id=order.seller_id,
        reason=data.reason.value,
        description=data.description,
        images=json.dumps(data.images) if data.images else None,
        status=ReturnStatus.PENDING.value,
        refund_amount=int(order.final_price),
    )
    db.add(return_req)
    await db.commit()
    await db.refresh(return_req)

    await crud_order_event.create_order_event(db, order.id, "RETURN_REQUESTED",
        f"Return requested: {data.reason.value}", actor_id=current_user.id)

    return return_req


@router.post("/{return_id}/respond")
async def respond_return(
    current_user: CurrentUser,
    db: SessionDep,
    return_id: uuid.UUID,
    data: ReturnRespond,
):
    """Seller phản hồi yêu cầu hoàn."""
    req = await get_return_by_id(db, return_id)
    if not req or req.seller_id != current_user.id:
        raise HTTPException(403, "Not your return request")
    if req.status != ReturnStatus.PENDING.value:
        raise HTTPException(400, "Already responded")

    if data.approve:
        req.status = ReturnStatus.SELLER_APPROVED.value
    else:
        req.status = ReturnStatus.SELLER_REJECTED.value
        req.admin_notes = data.message

    req.seller_responded_at = datetime.now(timezone.utc)
    db.add(req)
    await db.commit()

    await crud_order_event.create_order_event(db, req.order_id, "RETURN_RESPONDED",
        f"Seller {'approved' if data.approve else 'rejected'} return", actor_id=current_user.id)

    return {"status": req.status}


@router.post("/{return_id}/ship")
async def ship_return(
    current_user: CurrentUser,
    db: SessionDep,
    return_id: uuid.UUID,
    data: ReturnShipInput,
):
    """Buyer gửi tracking hàng hoàn."""
    req = await get_return_by_id(db, return_id)
    if not req or req.buyer_id != current_user.id:
        raise HTTPException(403, "Not your return request")
    if req.status != ReturnStatus.SELLER_APPROVED.value:
        raise HTTPException(400, "Seller has not approved yet")

    req.status = ReturnStatus.RETURN_SHIPPED.value
    req.return_tracking_number = data.return_tracking_number
    req.return_carrier = data.return_carrier
    req.buyer_shipped_at = datetime.now(timezone.utc)
    db.add(req)
    await db.commit()

    return {"status": req.status}


@router.post("/{return_id}/confirm-received")
async def confirm_return_received(
    current_user: CurrentUser,
    db: SessionDep,
    return_id: uuid.UUID,
):
    """Seller xác nhận đã nhận hàng hoàn -> trigger refund."""
    req = await get_return_by_id(db, return_id)
    if not req or req.seller_id != current_user.id:
        raise HTTPException(403, "Not your return request")
    if req.status != ReturnStatus.RETURN_SHIPPED.value:
        raise HTTPException(400, "Buyer has not shipped yet or already processed")

    order = await crud_order.get_order_by_id(db, req.order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    from app.crud import crud_escrow
    escrow = await crud_escrow.get_escrow_by_order_id(db, order.id)

    if order.payment_method == "wallet" and escrow and escrow.status == "funded":
        buyer_wallet = await get_wallet_by_user_id(db, order.buyer_id)
        if buyer_wallet:
            await unlock_balance(db, buyer_wallet.id, escrow.amount, order.id,
                description="Refund from return")

        escrow.status = "refunded"
        db.add(escrow)

        if req.return_fee > 0:
            seller_wallet = await get_wallet_by_user_id(db, order.seller_id)
            if seller_wallet:
                seller_wallet.balance -= req.return_fee
                db.add(seller_wallet)

        order.status = OrderStatus.RETURNED  # type: ignore[assignment]
        db.add(order)

        req.status = ReturnStatus.REFUNDED.value
        req.seller_received_at = datetime.now(timezone.utc)
        req.refunded_at = datetime.now(timezone.utc)
        db.add(req)

        await crud_order_event.create_order_event(db, order.id, "RETURN_REFUNDED",
            f"Return completed. Refunded {escrow.amount} to buyer", actor_id=current_user.id)

        await db.commit()
        return {"status": "refunded", "amount": escrow.amount}

    raise HTTPException(400, "Cannot refund this order")


@router.get("/my-requests")
async def get_my_return_requests(
    current_user: CurrentUser,
    db: SessionDep,
    skip: int = 0,
    limit: int = 20,
):
    """Lấy danh sách yêu cầu hoàn của user (buyer)."""
    from app.crud.crud_return import get_returns_for_buyer
    items, total = await get_returns_for_buyer(db, current_user.id, skip, limit)
    return {"items": items, "total": total}


@router.get("/my-seller-requests")
async def get_seller_return_requests(
    current_user: CurrentUser,
    db: SessionDep,
    skip: int = 0,
    limit: int = 20,
):
    """Lấy danh sách yêu cầu hoàn cho seller."""
    from app.crud.crud_return import get_returns_for_seller
    items, total = await get_returns_for_seller(db, current_user.id, skip, limit)
    return {"items": items, "total": total}
