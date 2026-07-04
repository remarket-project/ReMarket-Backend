import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
from openai import AsyncOpenAI
from sqlalchemy import select, func, asc, desc
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.enums import ConditionGrade, ListingStatus
from app.models.listing import Listing
from app.models.category import Category

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 9Router client (reuse pattern from moderation.py)
# ---------------------------------------------------------------------------

_nine_router_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _nine_router_client
    if _nine_router_client is None:
        _nine_router_client = AsyncOpenAI(
            base_url=settings.NINE_ROUTER_BASE_URL,
            api_key=settings.NINE_ROUTER_API_KEY or "sk-9router",
            timeout=httpx.Timeout(30.0, connect=5.0),
        )
    return _nine_router_client


# ---------------------------------------------------------------------------
# Condition label mapping for prompts
# ---------------------------------------------------------------------------

_CONDITION_LABELS = {
    ConditionGrade.BRAND_NEW: "Mới chưa dùng",
    ConditionGrade.LIKE_NEW: "Như mới",
    ConditionGrade.GOOD: "Tốt",
    ConditionGrade.FAIR: "Bình thường",
    ConditionGrade.POOR: "Kém",
}

# ---------------------------------------------------------------------------
# Cache (in-memory, simple TTL)
# ---------------------------------------------------------------------------

_suggestion_cache: dict[str, Any] = {}
_analysis_cache: dict[str, Any] = {}
_CACHE_TTL_SUGGESTION = 3600  # 1 hour
_CACHE_TTL_ANALYSIS = 1800    # 30 minutes


def _cache_get(cache: dict, key: str, ttl: int) -> Any | None:
    entry = cache.get(key)
    if entry:
        age = (datetime.now(timezone.utc) - entry["ts"]).total_seconds()
        if age < ttl:
            return entry["data"]
    return None


def _cache_set(cache: dict, key: str, data: Any) -> None:
    cache[key] = {"data": data, "ts": datetime.now(timezone.utc)}


# ---------------------------------------------------------------------------
# External reference generator (deterministic search URLs — no hallucination)
# ---------------------------------------------------------------------------

def _generate_external_refs(title: str) -> list[dict]:
    import urllib.parse
    query = urllib.parse.quote(f"{title}")
    return [
        {"source": "Shopee", "title": f"Tìm '{title}' trên Shopee", "search_url": f"https://shopee.vn/search?keyword={query}"},
        {"source": "Tiki", "title": f"Tìm '{title}' trên Tiki", "search_url": f"https://tiki.vn/search?q={query}"},
        {"source": "Lazada", "title": f"Tìm '{title}' trên Lazada", "search_url": f"https://www.lazada.vn/catalog/?q={query}"},
    ]


# ---------------------------------------------------------------------------
# Query similar listings from DB (embedding cosine similarity)
# ---------------------------------------------------------------------------

async def _query_similar_listings(
    db: Any,
    query_text: str,
    condition_grade: ConditionGrade | None = None,
    exclude_listing_id: str | None = None,
    limit: int = 10,
) -> list[dict]:
    from app.services.embeddings import embed_listing_text

    try:
        query_vec = await embed_listing_text(query_text)
        q = (
            select(Listing)
            .options(selectinload(Listing.seller))  # type: ignore[arg-type]
            .where(
                Listing.status == ListingStatus.ACTIVE,  # type: ignore[arg-type]
                Listing.embedding.isnot(None),  # type: ignore[union-attr]
            )
        )
        if condition_grade:
            q = q.where(Listing.condition_grade == condition_grade)  # type: ignore[arg-type]
        if exclude_listing_id:
            q = q.where(Listing.id != exclude_listing_id)  # type: ignore[arg-type]

        q = q.order_by(Listing.embedding.cosine_distance(query_vec)).limit(limit)  # type: ignore[union-attr]

        result = await db.execute(q)
        listings = list(result.scalars().all())
    except Exception as e:
        logger.warning("Embedding search failed: %s", e)
        listings = []

    return [
        {
            "id": str(l.id),
            "title": l.title,
            "price": float(l.price),
            "condition_grade": l.condition_grade.value,
            "location_summary": l.location_summary or "",
        }
        for l in listings
    ]


async def _query_price_stats(
    db: Any,
    category_id: uuid.UUID | str,
    condition_grade: ConditionGrade | None = None,
) -> dict:
    # Try exact match first
    query = select(
        func.avg(Listing.price),
        func.min(Listing.price),
        func.max(Listing.price),
        func.count(Listing.id),  # type: ignore[arg-type]
    ).where(Listing.status == ListingStatus.ACTIVE)  # type: ignore[arg-type]
    if category_id:
        query = query.where(Listing.category_id == category_id)  # type: ignore[arg-type]
    if condition_grade:
        query = query.where(Listing.condition_grade == condition_grade)  # type: ignore[arg-type]

    result = await db.execute(query)
    row = result.one()
    total_count = row[3] or 0

    # If too few results, broaden to same category only
    if total_count < 3:
        query2 = select(
            func.avg(Listing.price),
            func.min(Listing.price),
            func.max(Listing.price),
            func.count(Listing.id),  # type: ignore[arg-type]
        ).where(Listing.status == ListingStatus.ACTIVE)  # type: ignore[arg-type]
        if category_id:
            query2 = query2.where(Listing.category_id == category_id)  # type: ignore[arg-type]

        result2 = await db.execute(query2)
        row2 = result2.one()
        total_count2 = row2[3] or 0

        if total_count2 > total_count:
            avg_price = float(row2[0]) if row2[0] else 0
            min_price = float(row2[1]) if row2[1] else 0
            max_price = float(row2[2]) if row2[2] else 0
            return {
                "average_price": avg_price,
                "min_price": min_price,
                "max_price": max_price,
                "total_count": total_count2,
            }

    avg_price = float(row[0]) if row[0] else 0
    min_price = float(row[1]) if row[1] else 0
    max_price = float(row[2]) if row[2] else 0
    return {
        "average_price": avg_price,
        "min_price": min_price,
        "max_price": max_price,
        "total_count": total_count,
    }


async def _get_category_name(db: Any, category_id: uuid.UUID | str) -> str:
    result = await db.execute(select(Category.name).where(Category.id == category_id))  # type: ignore[arg-type]
    row = result.scalar_one_or_none()
    return row or "Không xác định"


# ---------------------------------------------------------------------------
# AI call with fallback chain
# ---------------------------------------------------------------------------

_PRIMARY_MODEL = "oc/deepseek-v4-flash-free"
_FALLBACK_MODEL = "oc/deepseek-v4-flash-free"


async def _call_ai(prompt: str, system_prompt: str) -> str | None:
    for model in [_PRIMARY_MODEL, _FALLBACK_MODEL]:
        try:
            client = _get_client()
            resp = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content
            if content:
                return content
        except Exception as e:
            logger.warning("Model %s failed: %s", model, e)
            continue
    return None


# ---------------------------------------------------------------------------
# Build prompts
# ---------------------------------------------------------------------------

_SELLER_SYSTEM_PROMPT = """Bạn là chuyên gia định giá sản phẩm tại Việt Nam, am hiểu cả giá mới và giá đồ cũ trên các sàn Chợ Tốt, Facebook Marketplace, Shopee, Tiki.

Nhiệm vụ: phân tích tổng hợp cả dữ liệu từ ReMarket và kiến thức thị trường thực tế của bạn để đề xuất giá bán hợp lý nhất.

Quy tắc:
- LUÔN kết hợp cả hai nguồn: (1) dữ liệu listings từ ReMarket được cung cấp và (2) kiến thức của bạn về giá thị trường thực tế tại Việt Nam
- Đánh giá chất lượng dữ liệu ReMarket: nếu số lượng listings ít (<3) hoặc giá quá thấp/cao bất thường, hãy ưu tiên kiến thức thị trường của bạn hơn
- Tham khảo giá mới trên thị trường và khấu hao theo tình trạng và thời gian sử dụng
- Đưa ra khoảng giá cạnh tranh, thực tế
- Giải thích ngắn gọn bằng tiếng Việt
- Kết quả PHẢI là JSON hợp lệ, không thêm text ngoài JSON

Trả về JSON với format:
{
  "suggested_price": float,      // giá đề xuất cụ thể (VNĐ)
  "price_range_min": float,      // giá thấp nhất trong khoảng đề xuất (VNĐ)
  "price_range_max": float,      // giá cao nhất trong khoảng đề xuất (VNĐ)
  "market_insight": string,      // 1-2 câu insight về thị trường (tiếng Việt)
  "analysis": string             // phân tích chi tiết ngắn (2-3 câu, tiếng Việt)
}"""

_BUYER_SYSTEM_PROMPT = """Bạn là chuyên gia tư vấn mua hàng đồ cũ tại Việt Nam.
Nhiệm vụ: đánh giá mức giá của một listing có hợp lý hay không bằng cách kết hợp dữ liệu từ ReMarket và kiến thức thị trường thực tế.

Quy tắc:
- LUÔN kết hợp cả hai nguồn: (1) dữ liệu listings ReMarket được cung cấp và (2) kiến thức thị trường thực tế của bạn
- Nếu dữ liệu ReMarket ít hoặc bất thường, ưu tiên dùng kiến thức thực tế về giá sản phẩm đó tại Việt Nam
- Đưa ra đánh giá trung thực: "rẻ", "hợp lý", "hơi cao", "cao"
- Đề xuất cụ thể cho người mua (có nên mua, nên thương lượng giá nào)
- Giải thích ngắn gọn bằng tiếng Việt
- Kết quả PHẢI là JSON hợp lệ, không thêm text ngoài JSON

Trả về JSON với format:
{
  "assessment": string,          // "rẻ" | "hợp lý" | "hơi cao" | "cao"
  "reasoning": string,           // lý do đánh giá (1-2 câu, tiếng Việt)
  "recommendation": string       // đề xuất cho người mua (1-2 câu, tiếng Việt)
}"""


def _build_seller_prompt(
    title: str,
    condition_label: str,
    category_name: str,
    similar: list[dict],
    stats: dict,
) -> str:
    similar_text = "\n".join(
        f"- {s['title']}: {s['price']:,.0f}đ ({s['condition_grade']})"
        for s in similar[:8]
    ) or "Không có dữ liệu tương tự."

    return f"""Sản phẩm: "{title}"
Danh mục: {category_name}
Tình trạng: {condition_label}

Dữ liệu thị trường từ ReMarket:
- Số lượng listing trong danh mục: {stats['total_count']}
- Giá trung bình: {stats['average_price']:,.0f}đ
- Khoảng giá: {stats['min_price']:,.0f}đ - {stats['max_price']:,.0f}đ

Các listing trong danh mục:
{similar_text}

Hãy phân tích và đề xuất giá bán hợp lý cho sản phẩm này.
QUAN TRỌNG: Luôn kết hợp cả dữ liệu ReMarket trên đây và kiến thức thực tế của bạn về giá thị trường Việt Nam. Nếu dữ liệu ReMarket ít hoặc sai lệch, hãy ưu tiên kiến thức thị trường thực tế."""


def _build_buyer_prompt(
    title: str,
    listing_price: float,
    condition_label: str,
    category_name: str,
    similar: list[dict],
    stats: dict,
) -> str:
    similar_text = "\n".join(
        f"- {s['title']}: {s['price']:,.0f}đ ({s['condition_grade']})"
        for s in similar[:8]
    ) or "Không có dữ liệu tương tự."

    return f"""Sản phẩm: "{title}"
Danh mục: {category_name}
Giá niêm yết: {listing_price:,.0f}đ
Tình trạng: {condition_label}

Dữ liệu thị trường từ ReMarket:
- Số lượng listing trong danh mục: {stats['total_count']}
- Giá trung bình: {stats['average_price']:,.0f}đ
- Khoảng giá: {stats['min_price']:,.0f}đ - {stats['max_price']:,.0f}đ

Các listing trong danh mục:
{similar_text}

Hãy đánh giá mức giá {listing_price:,.0f}đ có hợp lý không và đưa ra đề xuất.
QUAN TRỌNG: Luôn kết hợp cả dữ liệu ReMarket trên đây và kiến thức thực tế của bạn về giá thị trường Việt Nam. Nếu dữ liệu ReMarket ít hoặc sai lệch, hãy ưu tiên kiến thức thị trường thực tế."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_price_suggestion(
    db: Any,
    category_id: uuid.UUID,
    condition_grade: ConditionGrade,
    title: str,
    description: str | None = None,
) -> dict:
    cache_key = f"suggest:{category_id}:{condition_grade.value}:{title.lower().strip()[:50]}"
    cached = _cache_get(_suggestion_cache, cache_key, _CACHE_TTL_SUGGESTION)
    if cached:
        return cached

    condition_label = _CONDITION_LABELS.get(condition_grade, condition_grade.value)
    category_name = await _get_category_name(db, category_id)
    query_text = f"{title} {description or ''} {category_name}"
    similar = await _query_similar_listings(db, query_text, condition_grade)
    stats = await _query_price_stats(db, category_id, condition_grade)

    prompt = _build_seller_prompt(title, condition_label, category_name, similar, stats)
    ai_result = await _call_ai(prompt, _SELLER_SYSTEM_PROMPT)

    if ai_result:
        try:
            data = json.loads(ai_result)
        except json.JSONDecodeError:
            logger.warning("AI returned invalid JSON: %s", ai_result[:200])
            data = {}
    else:
        data = {}

    if not data.get("suggested_price"):
        data["suggested_price"] = stats["average_price"]
    if not data.get("price_range_min"):
        data["price_range_min"] = stats["min_price"]
    if not data.get("price_range_max"):
        data["price_range_max"] = stats["max_price"]
    if not data.get("market_insight"):
        data["market_insight"] = f"Có {stats['total_count']} sản phẩm tương tự, giá từ {stats['min_price']:,.0f}đ đến {stats['max_price']:,.0f}đ"
    if not data.get("analysis"):
        data["analysis"] = f"Giá trung bình thị trường là {stats['average_price']:,.0f}đ cho sản phẩm cùng danh mục và tình trạng."

    result = {
        "suggested_price": round(float(data["suggested_price"]), -3),
        "price_range_min": round(float(data["price_range_min"]), -3),
        "price_range_max": round(float(data["price_range_max"]), -3),
        "market_insight": data["market_insight"],
        "average_price": round(stats["average_price"], -3),
        "similar_listings": similar[:5],
        "external_references": _generate_external_refs(title),
        "analysis": data["analysis"],
    }

    _cache_set(_suggestion_cache, cache_key, result)
    return result


async def get_market_analysis(
    db: Any,
    listing_id: uuid.UUID,
    listing: Listing,
) -> dict:
    cache_key = f"analysis:{listing_id}"
    cached = _cache_get(_analysis_cache, cache_key, _CACHE_TTL_ANALYSIS)
    if cached:
        return cached

    title = listing.title
    listing_price = float(listing.price)
    condition_grade = listing.condition_grade
    category_id = listing.category_id
    condition_label = _CONDITION_LABELS.get(condition_grade, condition_grade.value)

    category_name = await _get_category_name(db, category_id)
    query_text = f"{title} {listing.description or ''} {category_name}"
    similar = await _query_similar_listings(
        db, query_text, condition_grade,
        exclude_listing_id=str(listing_id),
    )
    stats = await _query_price_stats(db, category_id, condition_grade)

    prompt = _build_buyer_prompt(title, listing_price, condition_label, category_name, similar, stats)
    ai_result = await _call_ai(prompt, _BUYER_SYSTEM_PROMPT)

    if ai_result:
        try:
            data = json.loads(ai_result)
        except json.JSONDecodeError:
            logger.warning("AI returned invalid JSON: %s", ai_result[:200])
            data = {}
    else:
        data = {}

    if not data.get("assessment"):
        if listing_price < stats["average_price"] * 0.85:
            data["assessment"] = "rẻ"
        elif listing_price <= stats["average_price"] * 1.1:
            data["assessment"] = "hợp lý"
        elif listing_price <= stats["average_price"] * 1.3:
            data["assessment"] = "hơi cao"
        else:
            data["assessment"] = "cao"

    if not data.get("reasoning"):
        data["reasoning"] = f"Giá trung bình các sản phẩm tương tự là {stats['average_price']:,.0f}đ, trong khi listing này được đăng với giá {listing_price:,.0f}đ."

    avg = stats["average_price"]
    if not data.get("recommendation"):
        if listing_price <= avg * 0.85:
            data["recommendation"] = "Đây là mức giá tốt so với thị trường. Bạn có thể yên tâm mua ngay."
        elif listing_price <= avg * 1.1:
            data["recommendation"] = "Mức giá này khá hợp lý, phù hợp với mặt bằng chung."
        elif listing_price <= avg * 1.3:
            data["recommendation"] = f"Giá hơi cao so với trung bình. Bạn nên thương lượng xuống khoảng {avg:,.0f}đ."
        else:
            data["recommendation"] = f"Giá khá cao so với thị trường. Tham khảo thêm các sản phẩm tương tự trước khi quyết định."

    result = {
        "listing_id": str(listing_id),
        "listing_price": listing_price,
        "assessment": data["assessment"],
        "average_price": round(avg, -3),
        "price_range_min": round(stats["min_price"], -3),
        "price_range_max": round(stats["max_price"], -3),
        "reasoning": data["reasoning"],
        "similar_listings": similar[:5],
        "external_references": _generate_external_refs(title),
        "recommendation": data["recommendation"],
    }

    _cache_set(_analysis_cache, cache_key, result)
    return result
