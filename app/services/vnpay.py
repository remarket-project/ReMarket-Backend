"""VNPay payment gateway integration (Sandbox).

Sandbox registration: https://sandbox.vnpayment.vn/devreg/
API docs: https://sandbox.vnpayment.vn/apis/
"""
import hashlib
import hmac
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

VNP_VERSION = "2.1.0"
VNP_COMMAND = "pay"
VNP_CURR_CODE = "VND"
VNP_LOCALE = "vn"


def _create_secure_hash(params: dict, hash_secret: str) -> str:
    """Create HMAC-SHA512 hash from sorted params.

    Sắp xếp các key theo alphabet, nối thành chuỗi key=value,
    dùng HMAC-SHA512 với hash_secret.
    """
    sorted_keys = sorted(params.keys())
    raw = "&".join(f"{k}={params[k]}" for k in sorted_keys)
    return hmac.new(
        hash_secret.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha512,
    ).hexdigest()


def create_payment_url(
    txn_ref: str,
    amount: int,
    return_url: str,
    ipn_url: str,
    order_info: str = "Nap vi ReMarket",
    locale: str = VNP_LOCALE,
) -> str:
    """Create a signed VNPay payment URL.

    Args:
        txn_ref: Mã giao dịch (duy nhất, không trùng)
        amount: Số tiền VND (sẽ tự động x100 theo format VNPay)
        return_url: Frontend redirect URL sau khi thanh toán
        ipn_url: Backend IPN URL nhận thông báo thanh toán
        order_info: Mô tả đơn hàng
        locale: Ngôn ngữ (vn/en)

    Returns:
        URL đã ký để redirect người dùng đến VNPay
    """
    params: dict[str, Any] = {
        "vnp_Amount": amount * 100,
        "vnp_Command": VNP_COMMAND,
        "vnp_CurrCode": VNP_CURR_CODE,
        "vnp_IpnUrl": ipn_url,
        "vnp_Locale": locale,
        "vnp_OrderInfo": order_info[:255],
        "vnp_OrderType": "other",
        "vnp_ReturnUrl": return_url,
        "vnp_TmnCode": settings.VNP_TMN_CODE,
        "vnp_TxnRef": txn_ref,
        "vnp_Version": VNP_VERSION,
    }

    params["vnp_SecureHash"] = _create_secure_hash(params, settings.VNP_HASH_SECRET)

    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{settings.VNP_API_URL}/paymentv2/vpcpay.html?{query}"


def verify_secure_hash(params: dict) -> bool:
    """Verify the HMAC-SHA512 signature from VNPay response.

    Args:
        params: Dict chứa tất cả params từ VNPay (bao gồm vnp_SecureHash)

    Returns:
        True nếu chữ ký hợp lệ
    """
    received_hash = params.pop("vnp_SecureHash", None)
    if not received_hash or not isinstance(received_hash, str):
        return False

    expected_hash = _create_secure_hash(params, settings.VNP_HASH_SECRET)
    return hmac.compare_digest(received_hash, expected_hash)


def verify_return_params(params: dict) -> bool:
    """Verify params from VNPay return URL (frontend redirect).

    Chỉ dùng để hiển thị kết quả, KHÔNG dùng để cập nhật số dư.
    """
    return verify_secure_hash(params.copy())


def verify_ipn_params(params: dict) -> bool:
    """Verify params from VNPay IPN (server-to-server).

    Đây là nguồn sự thật (source of truth) để cập nhật số dư.
    """
    return verify_secure_hash(params.copy())


async def query_transaction(txn_ref: str) -> dict:
    """Query transaction status from VNPay (QueryDr API).

    Args:
        txn_ref: Mã giao dịch cần tra cứu

    Returns:
        Dict chứa kết quả từ VNPay
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    params: dict[str, Any] = {
        "vnp_Command": "querydr",
        "vnp_TmnCode": settings.VNP_TMN_CODE,
        "vnp_TxnRef": txn_ref,
        "vnp_TransactionDate": now.strftime("%Y%m%d%H%M%S"),
        "vnp_Version": VNP_VERSION,
        "vnp_CreateDate": now.strftime("%Y%m%d%H%M%S"),
        "vnp_IpAddr": "127.0.0.1",
    }

    hash_params = {k: v for k, v in params.items() if v is not None}
    params["vnp_SecureHash"] = _create_secure_hash(hash_params, settings.VNP_HASH_SECRET)

    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{settings.VNP_API_URL}/merchant_webapi/api/transaction?{query}"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        logger.info("VNPay QueryDr result for %s: %s", txn_ref, data)
        return data


async def refund_transaction(
    txn_ref: str,
    amount: int,
    trans_date: str,
    user_ip: str = "127.0.0.1",
) -> dict:
    """Refund a transaction (Refund API).

    Args:
        txn_ref: Mã giao dịch gốc
        amount: Số tiền hoàn (VND)
        trans_date: Ngày giao dịch gốc (yyyyMMddHHmmss)
        user_ip: IP người dùng

    Returns:
        Dict chứa kết quả từ VNPay
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    params: dict[str, Any] = {
        "vnp_Command": "refund",
        "vnp_TmnCode": settings.VNP_TMN_CODE,
        "vnp_TxnRef": txn_ref,
        "vnp_Amount": amount * 100,
        "vnp_TransactionDate": trans_date,
        "vnp_Version": VNP_VERSION,
        "vnp_CreateDate": now.strftime("%Y%m%d%H%M%S"),
        "vnp_IpAddr": user_ip,
        "vnp_OrderInfo": "Hoan tien nap vi",
        "vnp_TransactionType": "03",
    }

    hash_params = {k: v for k, v in params.items() if v is not None}
    params["vnp_SecureHash"] = _create_secure_hash(hash_params, settings.VNP_HASH_SECRET)

    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{settings.VNP_API_URL}/merchant_webapi/api/transaction?{query}"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, data=params)
        resp.raise_for_status()
        data = resp.json()
        logger.info("VNPay Refund result for %s: %s", txn_ref, data)
        return data
