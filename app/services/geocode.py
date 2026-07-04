"""
Geocoding service using Nominatim (OpenStreetMap, free, no API key).
Rate limited: max 1 req/s (respect policy).

Vietnamese address normalization: removes "Phường/Quận/Thành phố/Huyện/Tỉnh" prefixes
that Nominatim cannot resolve, and appends ", Vietnam" for accuracy.
"""
import logging
import re

import httpx

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "ReMarket/1.0"

# Vietnamese administrative prefixes that confuse Nominatim
_VN_PREFIXES = re.compile(
    r"^(Phường|Xã|Thị trấn|Thị xã|Quận|Huyện|Thành phố|Tỉnh)\s+",
    re.IGNORECASE | re.UNICODE,
)


def _normalize_vn_address(part: str) -> str:
    """Strip Vietnamese admin prefix from an address part."""
    return _VN_PREFIXES.sub("", part.strip()).strip()


def _normalize_address_for_geocode(address: str) -> str:
    """
    Normalize a Vietnamese address for Nominatim geocoding.

    e.g. "433, Phường Xuân La, Quận Tây Hồ, Thành phố Hà Nội"
      → "433, Xuân La, Tây Hồ, Hà Nội, Vietnam"
    """
    parts = [p.strip() for p in address.split(",") if p.strip()]
    normalized = [_normalize_vn_address(p) for p in parts if p]
    # Deduplicate adjacent identical parts
    dedup: list[str] = []
    for p in normalized:
        if not dedup or p != dedup[-1]:
            dedup.append(p)
    result = ", ".join(dedup)
    if not result.lower().endswith("vietnam"):
        result += ", Vietnam"
    return result


async def _nominatim_search(address: str) -> tuple[float, float] | None:
    """Call Nominatim and return (lat, lng) or None."""
    try:
        params = {"q": address, "format": "json", "limit": 1}
        headers = {"User-Agent": USER_AGENT}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            if data:
                return (float(data[0]["lat"]), float(data[0]["lon"]))
        return None
    except Exception as e:
        logger.warning("Nominatim request failed for '%s': %s", address[:60], e)
        return None


async def geocode_address(address: str) -> tuple[float, float] | None:
    """
    Geocode a full Vietnamese address string to (lat, lng).

    Strategy:
    1. Try normalized address (prefixes stripped, Vietnam appended)
    2. If no result, try original address
    Returns None if both fail.
    """
    if not address or not address.strip():
        return None

    normalized = _normalize_address_for_geocode(address)
    result = await _nominatim_search(normalized)
    if result:
        logger.debug("Geocoded '%s' → %s", address[:60], result)
        return result

    # Fallback: try the original address as-is
    if normalized != address.strip():
        result = await _nominatim_search(address.strip())
        if result:
            logger.debug("Geocoded (fallback) '%s' → %s", address[:60], result)
            return result

    logger.warning("No geocoding result for: %s", address[:60])
    return None


def build_seller_address(location_summary: str | None) -> str:
    """Build full address string for the seller from listing's location_summary."""
    return location_summary.strip() if location_summary else ""


def build_shipping_address(
    shipping_address_detail: str | None,
    shipping_ward: str | None,
    shipping_district: str | None,
    shipping_province: str | None,
) -> str:
    """Build full address string for the buyer's shipping address."""
    parts = [p for p in [
        shipping_address_detail, shipping_ward,
        shipping_district, shipping_province,
    ] if p]
    return ", ".join(parts) if parts else ""
