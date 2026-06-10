"""Shipping API endpoints.

GHN integration: provinces, districts, wards, fee calculation, order creation,
webhook, return-order, and delivery-again.
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.crud import crud_escrow, crud_order, crud_order_event
from app.crud.crud_wallet import get_wallet_by_user_id, unlock_balance
from app.models.enums import ListingStatus, OrderStatus
from app.models.listing import Listing
from app.services import ghn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shipping", tags=["Shipping"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ProvinceOut(BaseModel):
    province_id: int
    province_name: str

class DistrictOut(BaseModel):
    district_id: int
    district_name: str

class WardOut(BaseModel):
    ward_code: str
    ward_name: str

class ServiceOut(BaseModel):
    service_id: int
    short_name: str
    service_type_id: int

class FeeRequest(BaseModel):
    to_district_id: int
    to_ward_code: str
    weight_grams: int = 500
    insurance_value: int = 0

class FeeOut(BaseModel):
    total: int
    service_fee: int
    insurance_fee: int
    vat: int

class ShippingOrderRequest(BaseModel):
    order_id: str
    to_name: str | None = None
    to_phone: str | None = None
    to_address: str | None = None
    to_ward_code: str | None = None
    to_district_id: int | None = None
    to_province_id: int | None = None
    weight_grams: int = 500
    insurance_value: int = 0
    note: str | None = None
    service_type_id: int = 2

class ShippingOrderOut(BaseModel):
    order_code: str
    expected_delivery_time: str
    total_fee: int
    tracking_url: str = ""

class AvailabilityOut(BaseModel):
    available: bool
    message: str = ""
    services: list[ServiceOut] = []

class ReturnOrderRequest(BaseModel):
    order_id: UUID
    reason: str | None = None

class DeliveryAgainRequest(BaseModel):
    order_id: UUID


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/provinces", response_model=list[ProvinceOut])
async def list_provinces():
    """Lấy danh sách tỉnh/thành phố từ GHN."""
    provinces = await ghn.get_provinces()
    return [ProvinceOut(province_id=p.province_id, province_name=p.province_name) for p in provinces]


@router.get("/districts", response_model=list[DistrictOut])
async def list_districts(province_id: int):
    """Lấy danh sách quận/huyện theo tỉnh."""
    districts = await ghn.get_districts(province_id)
    return [DistrictOut(district_id=d.district_id, district_name=d.district_name) for d in districts]


@router.get("/wards", response_model=list[WardOut])
async def list_wards(district_id: int):
    """Lấy danh sách phường/xã theo quận."""
    wards = await ghn.get_wards(district_id)
    return [WardOut(ward_code=w.ward_code, ward_name=w.ward_name) for w in wards]


@router.get("/services", response_model=list[ServiceOut])
async def list_services(to_district_id: int):
    """Lấy danh sách dịch vụ giao hàng khả dụng."""
    services = await ghn.get_available_services(to_district_id)
    return [ServiceOut(service_id=s.service_id, short_name=s.short_name, service_type_id=s.service_type_id) for s in services]


@router.post("/fee", response_model=FeeOut)
async def calculate_shipping_fee(data: FeeRequest):
    """Tính phí vận chuyển."""
    fee = await ghn.calculate_fee(
        to_district_id=data.to_district_id,
        to_ward_code=data.to_ward_code,
        weight_grams=data.weight_grams,
        insurance_value=data.insurance_value,
    )
    return FeeOut(total=fee.total, service_fee=fee.service_fee, insurance_fee=fee.insurance_fee, vat=fee.vat)


@router.post("/availability", response_model=AvailabilityOut)
async def check_availability(to_district_id: int, to_ward_code: str):
    """Kiểm tra GHN có phục vụ khu vực này không."""
    result = await ghn.get_service_availability(to_district_id, to_ward_code)
    return AvailabilityOut(
        available=result["available"],
        message=result.get("message", ""),
        services=result.get("services", []),
    )


@router.post("/create-order", response_model=ShippingOrderOut)
async def create_shipping_order(
    current_user: CurrentUser,
    db: SessionDep,
    data: ShippingOrderRequest,
):
    """Tạo đơn vận chuyển GHN cho order."""
    try:
        order_uuid = UUID(data.order_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="order_id không hợp lệ") from None
    order = await crud_order.get_order_by_id(db, order_uuid)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only seller can create shipping order")

    to_district_id = data.to_district_id or order.shipping_district_id or 0
    to_province_id = data.to_province_id or order.shipping_province_id or 0
    to_ward_code = data.to_ward_code or order.shipping_ward_code or ""

    to_address = data.to_address or ", ".join(filter(None, [
        order.shipping_address_detail,
        order.shipping_ward,
        order.shipping_district,
        order.shipping_province,
    ]))
    to_name = data.to_name or order.shipping_name or ""
    to_phone = data.to_phone or order.shipping_phone or ""

    cod_amount = int(order.final_price * 100) if order.payment_method == "cod" else 0

    result = await ghn.create_order(
        to_name=to_name,
        to_phone=to_phone,
        to_address=to_address,
        to_ward_code=to_ward_code,
        to_district_id=to_district_id,
        to_province_id=to_province_id,
        weight_grams=data.weight_grams,
        insurance_value=data.insurance_value,
        service_type_id=data.service_type_id,
        note=data.note,
        cod_amount=cod_amount,
    )

    order.shipping_provider = "ghn"
    order.shipping_service_type = data.service_type_id
    order.shipping_fee = Decimal(str(result.total_fee)) / Decimal("100")
    order.tracking_number = result.order_code
    order.expected_delivery_at = datetime.fromisoformat(result.expected_delivery_time.replace("Z", "+00:00"))
    order.status = OrderStatus.SHIPPING
    db.add(order)
    await db.commit()
    await db.refresh(order)

    await crud_order_event.create_order_event(db, order.id, "SHIPPING_ORDER_CREATED",
        f"Shipping order {result.order_code} created via GHN", actor_id=current_user.id)

    return ShippingOrderOut(
        order_code=result.order_code,
        expected_delivery_time=result.expected_delivery_time,
        total_fee=result.total_fee,
        tracking_url=f"https://donhang.ghn.vn/?order_code={result.order_code}",
    )


@router.post("/webhook")
async def shipping_webhook(request: Request, db: SessionDep):
    """GHN webhook: nhận cập nhật trạng thái giao hàng."""
    payload = await request.json()
    logger.info("GHN webhook received: %s", payload)

    order_code = payload.get("OrderCode") or payload.get("order_code")
    status_code = payload.get("Status") or payload.get("status")
    delivered_time = payload.get("DeliveryTime") or payload.get("delivery_time")
    reason = payload.get("Reason", "")

    if not order_code or not status_code:
        return {"code": 400, "message": "Missing OrderCode or Status"}

    order = await crud_order.get_order_by_tracking(db, order_code)
    if not order:
        logger.warning("Order not found for tracking: %s", order_code)
        return {"code": 404, "message": "Order not found"}

    if status_code in ("delivered", "DELIVERED"):
        await _handle_delivered(order, order_code, delivered_time, db)

    elif status_code in ("delivery_fail", "DELIVERY_FAIL"):
        await _handle_delivery_fail(order, order_code, reason, db)

    elif status_code in ("returned", "RETURNED"):
        await _handle_returned(order, order_code, db)

    elif status_code in ("cancel", "CANCELLED"):
        await _handle_cancelled(order, order_code, db)

    elif status_code in ("return", "returning", "waiting_to_return"):
        order.status = OrderStatus.RETURNING
        db.add(order)
        await crud_order_event.create_order_event(db, order.id, "RETURNING",
            f"GHN returning: {order_code}", actor_id=None)

    else:
        logger.info("GHN status update (ignored): %s -> %s", order_code, status_code)

    await db.commit()
    return {"code": 200, "message": "OK"}


async def _handle_delivered(order, order_code, delivered_time, db):
    order.status = OrderStatus.DELIVERED
    order.delivered_at = datetime.now(timezone.utc)
    if delivered_time:
        try:
            order.delivered_at = datetime.fromisoformat(delivered_time.replace("Z", "+00:00"))
        except ValueError:
            pass

    if order.payment_method == "wallet":
        now = datetime.now(timezone.utc)
        order.delivered_at_record = now
        from app.core.config import settings
        order.auto_complete_at = now + timedelta(hours=settings.ORDER_AUTO_COMPLETE_HOURS)
    elif order.payment_method == "cod":
        order.status = OrderStatus.COMPLETED

    db.add(order)
    await crud_order_event.create_order_event(db, order.id, "DELIVERED",
        f"GHN delivered: {order_code}", actor_id=None)


async def _handle_delivery_fail(order, order_code, reason, db):
    order.status = OrderStatus.RETURNING
    db.add(order)
    await crud_order_event.create_order_event(db, order.id, "RETURNING",
        f"GHN delivery failed, returning: {reason}")


async def _handle_returned(order, order_code, db):
    order.status = OrderStatus.RETURNED
    db.add(order)

    if order.payment_method == "wallet":
        escrow = await crud_escrow.get_escrow_by_order_id(db, order.id)
        if escrow and escrow.status == "funded":
            buyer_wallet = await get_wallet_by_user_id(db, order.buyer_id)
            if buyer_wallet:
                await unlock_balance(db, buyer_wallet.id, escrow.amount, order.id,
                    description=f"Refund from return: {order_code}")
            escrow.status = "refunded"
            db.add(escrow)

    listing_result = await db.execute(
        select(Listing).where(Listing.id == order.listing_id).with_for_update()
    )
    listing = listing_result.scalar_one_or_none()
    if listing:
        listing.status = ListingStatus.ACTIVE
        db.add(listing)

    await crud_order_event.create_order_event(db, order.id, "RETURNED",
        f"GHN returned: {order_code}", actor_id=None)


async def _handle_cancelled(order, order_code, db):
    order.status = OrderStatus.CANCELLED
    db.add(order)

    escrow = await crud_escrow.get_escrow_by_order_id(db, order.id)
    if escrow and escrow.status == "funded":
        buyer_wallet = await get_wallet_by_user_id(db, order.buyer_id)
        if buyer_wallet:
            await unlock_balance(db, buyer_wallet.id, escrow.amount, order.id,
                description=f"Refund from cancel: {order_code}")
        escrow.status = "refunded"
        db.add(escrow)

    listing_result = await db.execute(
        select(Listing).where(Listing.id == order.listing_id).with_for_update()
    )
    listing = listing_result.scalar_one_or_none()
    if listing:
        listing.status = ListingStatus.ACTIVE
        db.add(listing)

    await crud_order_event.create_order_event(db, order.id, "CANCELLED",
        f"GHN cancelled: {order_code}", actor_id=None)


@router.post("/return-order")
async def return_shipping_order(
    current_user: CurrentUser,
    db: SessionDep,
    data: ReturnOrderRequest,
):
    """Seller yêu cầu GHN trả hàng về."""
    order = await crud_order.get_order_by_id(db, data.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only seller can request return")
    if order.status not in (OrderStatus.SHIPPING,):
        raise HTTPException(status_code=400, detail="Order must be shipping to return")
    if not order.tracking_number:
        raise HTTPException(status_code=400, detail="No tracking number")

    result = await ghn.return_order([order.tracking_number])
    if result and result[0].get("result"):
        order.status = OrderStatus.RETURNING
        db.add(order)
        await db.commit()
        await crud_order_event.create_order_event(db, order.id, "RETURN_ORDERED",
            f"Return requested for {order.tracking_number}", actor_id=current_user.id)
        return {"status": "returning", "message": "Return requested successfully", "detail": result[0]}
    raise HTTPException(status_code=502, detail=f"GHN return failed: {result}")


@router.post("/delivery-again")
async def delivery_again_shipping(
    current_user: CurrentUser,
    db: SessionDep,
    data: DeliveryAgainRequest,
):
    """Seller yêu cầu GHN giao lại."""
    order = await crud_order.get_order_by_id(db, data.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only seller can request delivery again")
    if order.status != OrderStatus.SHIPPING:
        raise HTTPException(status_code=400, detail="Order must be shipping to retry delivery")
    if not order.tracking_number:
        raise HTTPException(status_code=400, detail="No tracking number")

    result = await ghn.delivery_again([order.tracking_number])
    if result and result[0].get("result"):
        order.status = OrderStatus.SHIPPING
        db.add(order)
        await db.commit()
        await crud_order_event.create_order_event(db, order.id, "DELIVERY_AGAIN",
            f"Delivery again requested for {order.tracking_number}", actor_id=current_user.id)
        return {"status": "shipping", "message": "Delivery again requested", "detail": result[0]}
    raise HTTPException(status_code=502, detail=f"GHN delivery-again failed: {result}")
