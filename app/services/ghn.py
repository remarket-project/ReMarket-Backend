"""GHN (Giao Hàng Nhanh) shipping service integration.

Sandbox docs: https://dev-online-gateway.ghn.vn/
API Docs: https://api.ghn.vn/home/docs/detail
"""
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Response shapes (dataclasses for internal use)
# ---------------------------------------------------------------------------

@dataclass
class GHNProvince:
    province_id: int
    province_name: str
    code: str


@dataclass
class GHNDistrict:
    district_id: int
    district_name: str
    code: str
    province_id: int


@dataclass
class GHNWard:
    ward_code: str
    ward_name: str
    district_id: int


@dataclass
class GHNServiceType:
    service_id: int
    short_name: str
    service_type_id: int


@dataclass
class GHNShippingFee:
    total: int
    service_fee: int
    insurance_fee: int
    vat: int


@dataclass
class GHNOrderResult:
    order_code: str
    expected_delivery_time: str
    total_fee: int
    status: str


# ---------------------------------------------------------------------------
# HTTP client helpers
# ---------------------------------------------------------------------------

def _headers() -> dict[str, str]:
    return {
        "Token": settings.GHN_TOKEN,
        "ShopId": str(settings.GHN_SHOP_ID),
        "Content-Type": "application/json",
    }


def _shop_params() -> dict[str, Any]:
    return {
        "from_province": settings.GHN_FROM_PROVINCE_ID,
        "from_district": settings.GHN_FROM_DISTRICT_ID,
        "from_ward": settings.GHN_FROM_WARD_CODE,
    }


async def _get(path: str, params: dict | None = None) -> dict[str, Any]:
    url = f"{settings.GHN_API_URL}{path}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 200:
            raise ValueError(f"GHN API error [{data.get('code')}]: {data.get('message', data)}")
        return data["data"]


async def _post(path: str, body: dict) -> dict[str, Any]:
    url = f"{settings.GHN_API_URL}{path}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, headers=_headers(), json=body)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 200:
            raise ValueError(f"GHN API error [{data.get('code')}]: {data.get('message', data)}")
        return data["data"]


# ---------------------------------------------------------------------------
# Helper: convert GHN PascalCase response keys → snake_case dataclass fields
# ---------------------------------------------------------------------------

def _to_snake(name: str) -> str:
    """Convert PascalCase to snake_case (e.g. ProvinceID → province_id)."""
    import re
    name = re.sub(r"(?<=[a-z])([A-Z])", r"_\1", name)
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    return name.lower()


_GHN_KEY_MAP = {
    "ProvinceID": "province_id", "ProvinceName": "province_name",
    "Code": "code", "DistrictID": "district_id", "DistrictName": "district_name",
    "WardCode": "ward_code", "WardName": "ward_name",
    "ServiceID": "service_id", "ShortName": "short_name", "ServiceTypeID": "service_type_id",
    "Total": "total", "ServiceFee": "service_fee", "InsuranceFee": "insurance_fee", "VAT": "vat",
}


def _parse_dataclass(dc_type: type, data: dict) -> Any:
    """Map GHN PascalCase keys → snake_case and keep only valid fields."""
    fields = dc_type.__dataclass_fields__
    kwargs = {}
    for k, v in data.items():
        key = _GHN_KEY_MAP.get(k, _to_snake(k))
        if key in fields:
            kwargs[key] = v
    return dc_type(**kwargs)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_provinces() -> list[GHNProvince]:
    raw = await _get("/master-data/province")
    result = []
    for p in raw:
        pid = p.get("ProvinceID")
        pname = p.get("ProvinceName")
        code = p.get("Code", "")
        result.append(GHNProvince(province_id=pid, province_name=pname, code=code))
    return result


async def get_districts(province_id: int) -> list[GHNDistrict]:
    raw = await _get("/master-data/district", {"province_id": province_id})
    result = []
    for d in raw:
        result.append(GHNDistrict(
            district_id=d.get("DistrictID"),
            district_name=d.get("DistrictName"),
            code=d.get("Code", ""),
            province_id=d.get("ProvinceID"),
        ))
    return result


async def get_wards(district_id: int) -> list[GHNWard]:
    raw = await _get("/master-data/ward", {"district_id": district_id})
    result = []
    for w in raw:
        result.append(GHNWard(
            ward_code=w.get("WardCode"),
            ward_name=w.get("WardName"),
            district_id=w.get("DistrictID"),
        ))
    return result


async def get_available_services(to_district_id: int) -> list[GHNServiceType]:
    raw = await _post("/v2/shipping-order/available-services", {
        "shop_id": settings.GHN_SHOP_ID,
        "from_district": settings.GHN_FROM_DISTRICT_ID,
        "to_district": to_district_id,
    })
    result = []
    for s in raw:
        result.append(GHNServiceType(
            service_id=s.get("ServiceID"),
            short_name=s.get("ShortName"),
            service_type_id=s.get("ServiceTypeID"),
        ))
    return result


async def calculate_fee(
    to_district_id: int,
    to_ward_code: str,
    weight_grams: int = 500,
    length_cm: int = 20,
    width_cm: int = 15,
    height_cm: int = 10,
    insurance_value: int = 0,
    service_type_id: int | None = None,
    coupon: str | None = None,
) -> GHNShippingFee:
    body = {
        "from_district_id": settings.GHN_FROM_DISTRICT_ID,
        "from_ward_code": settings.GHN_FROM_WARD_CODE,
        "to_district_id": to_district_id,
        "to_ward_code": to_ward_code,
        "weight": weight_grams,
        "length": length_cm,
        "width": width_cm,
        "height": height_cm,
        "insurance_value": insurance_value,
        "service_type_id": service_type_id or 2,
        "coupon": coupon,
    }
    raw = await _post("/v2/fee/fee", body)
    return GHNShippingFee(
        total=raw.get("total", 0),
        service_fee=raw.get("service_fee", 0),
        insurance_fee=raw.get("insurance_fee", 0),
        vat=raw.get("vat", 0),
    )


async def create_order(
    to_name: str,
    to_phone: str,
    to_address: str,
    to_ward_code: str,
    to_district_id: int,
    to_province_id: int,
    weight_grams: int = 500,
    length_cm: int = 20,
    width_cm: int = 15,
    height_cm: int = 10,
    insurance_value: int = 0,
    service_type_id: int = 2,
    note: str | None = None,
    cod_amount: int = 0,
) -> GHNOrderResult:
    body = {
        "payment_type_id": 2,
        "note": note or "",
        "required_note": "CHOXEMHANGKHONGTHU",
        "from_name": settings.PROJECT_NAME,
        "from_phone": settings.GHN_FROM_WARD_CODE or "0900000000",
        "from_address": "ReMarket Shop",
        "from_ward_code": settings.GHN_FROM_WARD_CODE,
        "from_district_id": settings.GHN_FROM_DISTRICT_ID,
        "from_province_id": settings.GHN_FROM_PROVINCE_ID,
        "to_name": to_name,
        "to_phone": to_phone,
        "to_address": to_address,
        "to_ward_code": to_ward_code,
        "to_district_id": to_district_id,
        "to_province_id": to_province_id,
        "cod_amount": cod_amount,
        "weight": weight_grams,
        "length": length_cm,
        "width": width_cm,
        "height": height_cm,
        "insurance_value": insurance_value,
        "service_type_id": service_type_id,
        "service_id": 0,
    }
    data = await _post("/v2/shipping-order/create", body)
    return GHNOrderResult(
        order_code=data.get("order_code", ""),
        expected_delivery_time=data.get("expected_delivery_time", ""),
        total_fee=data.get("total_fee", 0),
        status=data.get("status", ""),
    )


async def get_order_info(order_code: str) -> dict[str, Any]:
    return await _post("/v2/shipping-order/detail", {"order_code": order_code})


async def cancel_order_ghn(order_code: str) -> dict[str, Any]:
    return await _post("/v2/shipping-order/cancel", {"order_code": order_code})


async def return_order(order_codes: list[str]) -> list[dict[str, Any]]:
    """Gọi GHN API để yêu cầu trả hàng.
    
    Chỉ áp dụng khi trạng thái đơn hiện tại là: storing, waiting_to_return
    Docs: https://api.ghn.vn/home/docs/detail?id=72
    """
    data = await _post("/v2/switch-status/return", {
        "order_codes": order_codes
    })
    return data if isinstance(data, list) else [data]


async def delivery_again(order_codes: list[str]) -> list[dict[str, Any]]:
    """Gọi GHN API để yêu cầu giao lại.
    
    Docs: https://api.ghn.vn/home/docs/detail?id=65
    """
    data = await _post("/v2/switch-status/delivery-again", {
        "order_codes": order_codes
    })
    return data if isinstance(data, list) else [data]


async def get_service_availability(to_district_id: int, to_ward_code: str) -> dict[str, Any]:
    """Check if GHN serves the given location."""
    try:
        services = await get_available_services(to_district_id)
        if not services:
            return {"available": False, "message": "Không có dịch vụ giao hàng đến khu vực này"}
        return {"available": True, "services": [{"id": s.service_id, "name": s.short_name} for s in services]}
    except Exception as e:
        logger.warning("GHN availability check failed: %s", e)
        return {"available": False, "message": "Không thể kiểm tra dịch vụ giao hàng"}


def verify_webhook_signature(payload: dict, signature: str) -> bool:
    """Verify GHN webhook signature (if GHN provides one).
    GHN uses HMAC-SHA256 with API token."""
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    expected = hashlib.sha256((raw + settings.GHN_TOKEN).encode()).hexdigest()
    return signature == expected
