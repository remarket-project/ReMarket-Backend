"""PayOS payment gateway integration.

Sandbox docs: https://doc-sandbox.payos.vn/
API Docs: https://api-sandbox.payos.vn/
"""
import hashlib
import hmac
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PayOSPaymentLink:
    bin: str = ""
    account_number: str = ""
    amount: int = 0
    description: str = ""
    order_code: str = ""
    currency: str = "VND"
    payment_link_id: str = ""
    status: str = ""
    checkout_url: str = ""
    qr_code: str = ""
    transactions: list[dict] = field(default_factory=list)
    created_at: str = ""
    cancelled_at: str | None = None


# ---------------------------------------------------------------------------
# Signature helpers
# ---------------------------------------------------------------------------

def _sort_obj(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _sort_obj(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_sort_obj(v) for v in obj]
    return obj


def _create_signature(data: dict) -> str:
    sorted_data = _sort_obj(data)
    raw = urlencode(sorted_data)
    return hmac.new(
        settings.PAYOS_CHECKSUM_KEY.encode(),  # type: ignore[arg-type]
        raw.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_webhook(data: dict, signature: str) -> bool:
    return hmac.compare_digest(_create_signature(data), signature)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

async def _post(path: str, body: dict) -> dict[str, Any]:
    url = f"{settings.PAYOS_API_URL}{path}"  # type: ignore[arg-type]
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url,
            json=body,
            headers={
                "x-client-id": settings.PAYOS_CLIENT_ID,  # type: ignore[arg-type]
                "x-api-key": settings.PAYOS_API_KEY,  # type: ignore[arg-type]
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "00":
            raise ValueError(f"PayOS API error [{data.get('code')}]: {data.get('desc', data)}")
        return data["data"]


async def _get(path: str) -> dict[str, Any]:
    url = f"{settings.PAYOS_API_URL}{path}"  # type: ignore[arg-type]
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            url,
            headers={
                "x-client-id": settings.PAYOS_CLIENT_ID,  # type: ignore[arg-type]
                "x-api-key": settings.PAYOS_API_KEY,  # type: ignore[arg-type]
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "00":
            raise ValueError(f"PayOS API error [{data.get('code')}]: {data.get('desc', data)}")
        return data["data"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def create_payment_link(
    order_code: str,
    amount: int,
    description: str,
    cancel_url: str | None = None,
    return_url: str | None = None,
    buyer_name: str | None = None,
    buyer_email: str | None = None,
    buyer_phone: str | None = None,
    buyer_address: str | None = None,
    items: list[dict] | None = None,
    expired_at: int | None = None,
) -> PayOSPaymentLink:
    """Create a PayOS payment link.

    Args:
        order_code: Mã đơn hàng (duy nhất, dùng để xác định webhook)
        amount: Số tiền (VND)
        description: Mô tả (tối đa 25 ký tự)
        cancel_url: URL chuyển hướng khi hủy
        return_url: URL chuyển hướng khi thành công
        buyer_name, buyer_email, buyer_phone, buyer_address: Thông tin người mua
        items: Danh sách sản phẩm [{"name": str, "quantity": int, "price": int}]
        expired_at: Unix timestamp hết hạn

    Returns:
        PayOSPaymentLink chứa checkout_url và qr_code
    """
    body: dict[str, Any] = {
        "orderCode": int(order_code.replace("-", "")[:18]),
        "amount": amount,
        "description": description[:25],
        "cancelUrl": cancel_url or f"{settings.FRONTEND_HOST}/payment/cancel",
        "returnUrl": return_url or f"{settings.FRONTEND_HOST}/payment/success",
    }
    if buyer_name:
        body["buyerName"] = buyer_name
    if buyer_email:
        body["buyerEmail"] = buyer_email
    if buyer_phone:
        body["buyerPhone"] = buyer_phone
    if buyer_address:
        body["buyerAddress"] = buyer_address
    if items:
        body["items"] = items
    if expired_at:
        body["expiredAt"] = expired_at

    body["signature"] = _create_signature(body)
    data = await _post("/v2/payment-requests", body)
    return PayOSPaymentLink(**data)


async def get_payment_info(order_code: str) -> PayOSPaymentLink:
    """Get payment link info by order code."""
    path = f"/v2/payment-requests/{order_code}"
    data = await _get(path)
    return PayOSPaymentLink(**data)


async def cancel_payment_link(order_code: str) -> PayOSPaymentLink:
    """Cancel a payment link by order code."""
    path = f"/v2/payment-requests/{order_code}/cancel"
    data = await _post(path, {})
    return PayOSPaymentLink(**data)


def confirm_webhook(webhook_url: str) -> bool:
    """Confirm webhook URL with PayOS (required once per env).
    Called manually when deploying.
    """
    import httpx as sync_httpx
    resp = sync_httpx.post(
        f"{settings.PAYOS_API_URL}/confirm-webhook",  # type: ignore[arg-type]
        json={"webhookUrl": webhook_url},
        headers={
            "x-client-id": settings.PAYOS_CLIENT_ID,  # type: ignore[arg-type]
            "x-api-key": settings.PAYOS_API_KEY,  # type: ignore[arg-type]
            "Content-Type": "application/json",
        },
    )
    resp.raise_for_status()
    return resp.json().get("code") == "00"
