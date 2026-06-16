import json
import logging
import math
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.ai_client import ai_client
from app.core.exceptions import AllModelsExhaustedError
from app.db.session import AsyncSessionLocal
from app.models.enums import ListingStatus
from app.models.faq import FaqChunk
from app.models.listing import Listing
from app.services.faq_cache import faq_cache

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Bạn là trợ lý ảo thông minh của ReMarket - chợ mua bán C2C hàng đầu Việt Nam.
Luôn trả lời bằng tiếng Việt, tự nhiên, thân thiện, tối đa 300 từ.
Sử dụng các công cụ được cung cấp để tra cứu thông tin chính xác.

NĂNG LỰC:
1. search_faq() — Trả lời câu hỏi về chính sách, phí, hướng dẫn, quy trình
2. search_products(keyword, min_price, max_price, category) — Tìm sản phẩm thông minh
3. get_product_detail(product_id) — Xem chi tiết sản phẩm (giá, mô tả, tình trạng)
4. get_trending_products() — Xem sản phẩm thịnh hành / bán chạy

VÍ DỤ TỐT:
- "tìm iphone giá dưới 15 triệu" → search_products("iphone", max_price=15000000)
- "có laptop nào tốt không?" → search_products("laptop")
- "sản phẩm nào đang hot?" → get_trending_products()
- "cho tôi xem thông tin sp123" → get_product_detail("sp123")
- "phí giao dịch bao nhiêu?" → search_faq("phí giao dịch")

QUY TẮC AN TOÀN (TUYỆT ĐỐI KHÔNG trả lời):
- Nội dung khiêu dâm, tình dục, hẹn hò
- Bạo lực, khủng bố, vũ khí
- Hack, gian lận, lừa đảo, đánh cắp tài khoản
- Ma túy, chất cấm, thuốc kích thích
- Chia sẻ thông tin cá nhân (số điện thoại, địa chỉ, CMND/CCCD)
- Nội dung chính trị, tôn giáo nhạy cảm
- Bất kỳ giao dịch/phát ngôn vi phạm pháp luật Việt Nam
- Tự hủy hoại bản thân, tự tử

KHI GẶP CÂU HỎI VI PHẠM:
→ Từ chối lịch sự, ví dụ: "Xin lỗi, mình không thể hỗ trợ câu hỏi này. Bạn cần giúp gì về mua bán trên ReMarket không?"

KHI KHÔNG CHẮC CHẮN:
→ "Mình không đủ thông tin để trả lời chính xác. Bạn muốn mình tìm sản phẩm hoặc tra cứu chính sách giúp bạn không?"

Chào hỏi / cảm ơn → trả lời thân thiện, không cần gọi công cụ.
"""

TOOLS = [
    {
        "name": "search_faq",
        "description": "Tìm câu trả lời trong cơ sở dữ liệu FAQ về chính sách, phí, escrow, hướng dẫn đăng tin, hủy đơn, v.v.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Câu hỏi cần tìm kiếm (tiếng Việt)",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_products",
        "description": "Tìm kiếm sản phẩm thông minh trên ReMarket. Hỗ trợ tìm theo từ khóa, khoảng giá, danh mục. Kết quả trả về gồm tên, giá, tình trạng, địa điểm.",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "Từ khóa tìm kiếm (vd: iphone, laptop, đồ gia dụng)",
                },
                "min_price": {
                    "type": "number",
                    "description": "Giá tối thiểu (VNĐ)",
                },
                "max_price": {
                    "type": "number",
                    "description": "Giá tối đa (VNĐ)",
                },
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "get_product_detail",
        "description": "Xem thông tin chi tiết một sản phẩm trên ReMarket: tên, giá, mô tả, tình trạng, người bán, địa điểm.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "string",
                    "description": "ID của sản phẩm (UUID)",
                }
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "get_trending_products",
        "description": "Lấy danh sách sản phẩm nổi bật, thịnh hành trên ReMarket.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]

MAX_HISTORY = 8
SIMILARITY_THRESHOLD = 0.75


# ─── Main entry ──────────────────────────────────────────────────

async def ask_faq(question: str, history: list[dict] | None = None) -> dict:
    """
    Xử lý câu hỏi — Gemini ưu tiên, fallback local RAG khi hết quota.

    Returns:
        {"answer": str, "source": str | None, "mode": "gemini" | "local_rag"}
    """
    question = question.strip()
    if not question:
        return {"answer": "Vui lòng nhập câu hỏi.", "source": None, "mode": "local_rag"}

    if not history:
        cached = faq_cache.get(question)
        if cached:
            logger.info("FAQ cache hit: %s", question[:50])
            return cached

    try:
        result = await _ask_gemini(question, history)
        if not history and result.get("source") is not None and result.get("mode") == "gemini":
            faq_cache.set(question, result)
        return result
    except AllModelsExhaustedError:
        logger.info("All Gemini models exhausted — falling back to local RAG")

    return await _ask_local_rag(question)


# ─── Gemini flow ─────────────────────────────────────────────────

async def _ask_gemini(question: str, history: list[dict] | None) -> dict:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if history:
        for msg in history[-MAX_HISTORY:]:
            messages.append(msg)

    messages.append({"role": "user", "content": question})

    max_tool_rounds = 3
    found_products: list[dict] = []
    found_faq_answer: str | None = None

    for _ in range(max_tool_rounds):
        try:
            raw_response = await ai_client.chat(messages, tools=TOOLS)
        except AllModelsExhaustedError:
            raise
        except Exception as e:
            logger.error("Gemini chat failed: %s", e)
            raise AllModelsExhaustedError(str(e))

        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError:
            break

        if "function_call" not in parsed:
            break

        fc = parsed["function_call"]
        tool_fn = TOOL_DISPATCH.get(fc["name"])
        if not tool_fn:
            logger.warning("Unknown tool call: %s", fc["name"])
            break

        try:
            args = fc["args"] if isinstance(fc["args"], dict) else {}
            result = await tool_fn(args)
        except Exception as e:
            logger.error("Tool %s failed: %s", fc["name"], e)
            break

        # Track structured data from tool results
        if fc["name"] in ("search_products", "get_trending_products"):
            found_products.extend(result.get("products", []))
        elif fc["name"] == "get_product_detail" and result.get("found"):
            found_products.append(result["product"])
        elif fc["name"] == "search_faq" and result.get("found"):
            found_faq_answer = result.get("answer")

        messages.append({"role": "model", "content": raw_response})
        messages.append({"role": "user", "content": json.dumps(result, ensure_ascii=False)})

    try:
        final_answer = await ai_client.chat(messages)
    except AllModelsExhaustedError:
        raise
    except Exception as e:
        logger.error("Gemini final chat failed: %s", e)
        raise AllModelsExhaustedError(str(e))

    # Generate suggested actions based on context
    suggested_actions = _generate_suggested_actions(found_products, final_answer, bool(found_faq_answer))

    return {
        "answer": final_answer,
        "products": found_products,
        "suggested_actions": suggested_actions,
        "source": "ai_assist",
        "mode": "gemini",
    }


# ─── Local RAG Fallback (không cần Gemini) ──────────────────────

async def _ask_local_rag(question: str) -> dict:
    """
    Trả lời bằng local RAG — không cần Gemini.
    1. Embed câu hỏi bằng local E5
    2. Search FAQ (pgvector cosine similarity)
    3. Nếu match ≥ threshold → trả câu trả lời
    4. Nếu không → greeting + FAQ list
    """
    query_vec = await ai_client.embed_one(question, prefix="query: ")
    if not query_vec:
        return _fallback_greeting(question)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FaqChunk)
            .where(FaqChunk.embedding.isnot(None))  # type: ignore[attr-defined]
            .order_by(FaqChunk.embedding.cosine_distance(query_vec))  # type: ignore[attr-defined]
            .limit(1)
        )
        chunk = result.scalar_one_or_none()

    if chunk:
        distance = _cosine_distance(query_vec, chunk.embedding or [])
        similarity = 1.0 - distance
        logger.info("Local RAG match: similarity=%.4f, question=%s", similarity, chunk.question[:50])

        if similarity >= SIMILARITY_THRESHOLD:
            return {
                "answer": chunk.answer,
                "source": chunk.question,
                "mode": "local_rag",
            }

    return _fallback_greeting(question)


def _cosine_distance(vec1: list[float], vec2: list[float]) -> float:
    if not vec1 or not vec2:
        return 1.0
    dot = sum(a * b for a, b in zip(vec1, vec2, strict=False))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 1.0
    return 1.0 - (dot / (norm1 * norm2))


def _fallback_greeting(question: str) -> dict:
    q_lower = question.lower().strip()
    greetings = ["xin chào", "chào", "hello", "hi", "hey"]
    thanks = ["cảm ơn", "thanks", "thank"]

    if any(g in q_lower for g in greetings):
        return {
            "answer": "Chào bạn! Tôi là trợ lý ReMarket. Tôi có thể giúp gì cho bạn hôm nay?",
            "source": None,
            "mode": "local_rag",
        }
    if any(t in q_lower for t in thanks):
        return {
            "answer": "Cảm ơn bạn! Nếu cần hỗ trợ thêm, đừng ngần ngại hỏi tôi nhé.",
            "source": None,
            "mode": "local_rag",
        }

    return {
        "answer": (
            "Xin lỗi, hiện tại hệ thống AI đã đạt giới hạn requests hôm nay. "
            "Tôi chỉ có thể trả lời các câu hỏi thường gặp sau:\n\n"
            "• Làm thế nào để đăng tin bán hàng?\n"
            "• Thanh toán qua escrow hoạt động thế nào?\n"
            "• Phí giao dịch trên ReMarket là bao nhiêu?\n"
            "• Làm sao để liên hệ với người bán?\n"
            "• Tôi có thể hủy đơn hàng không?\n\n"
            "Hoặc bạn có thể gửi email đến support@remarket.vn để được hỗ trợ trực tiếp."
        ),
        "source": None,
        "mode": "local_rag",
    }


# ─── Tool execution ──────────────────────────────────────────────

async def _execute_search_faq(query: str) -> dict:
    query_vec = await ai_client.embed_one(query, prefix="query: ")
    if not query_vec:
        return {"found": False}

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FaqChunk)
            .where(FaqChunk.embedding.isnot(None))  # type: ignore[attr-defined]
            .order_by(FaqChunk.embedding.cosine_distance(query_vec))  # type: ignore[attr-defined]
            .limit(1)
        )
        chunk = result.scalar_one_or_none()

    if chunk:
        return {
            "found": True,
            "question": chunk.question,
            "answer": chunk.answer,
        }
    return {"found": False}


async def _execute_search_products(keyword: str, min_price: float | None = None, max_price: float | None = None) -> dict:
    query_vec = await ai_client.embed_one(keyword, prefix="query: ")

    async with AsyncSessionLocal() as db:
        query = (
            select(Listing)
            .options(selectinload(Listing.seller), selectinload(Listing.images))
            .where(Listing.status == ListingStatus.ACTIVE)
        )

        if min_price is not None:
            query = query.where(Listing.price >= min_price)  # type: ignore[arg-type]
        if max_price is not None:
            query = query.where(Listing.price <= max_price)  # type: ignore[arg-type]

        if query_vec:
            query = query.where(Listing.embedding.isnot(None))  # type: ignore[attr-defined]
            query = query.order_by(Listing.embedding.cosine_distance(query_vec))  # type: ignore[attr-defined]
        else:
            keyword_filter = f"%{keyword}%"
            query = query.where(
                Listing.title.ilike(keyword_filter) | Listing.description.ilike(keyword_filter)  # type: ignore[arg-type]
            )
            query = query.order_by(Listing.created_at.desc())  # type: ignore[attr-defined]

        result = await db.execute(query.limit(10))
        items = result.scalars().all()

    products = []
    for item in items:
        primary_img = next((img.image_url for img in (item.images or []) if img.is_primary), None)
        if not primary_img and item.images:
            primary_img = item.images[0].image_url
        products.append({
            "id": str(item.id),
            "title": item.title,
            "price": float(item.price) if item.price else 0,
            "condition": item.condition_grade or "unknown",
            "location": item.location_summary or "",
            "seller": item.seller.full_name if item.seller else "Unknown",
            "image_url": primary_img,
            "created_at": item.created_at.isoformat() if item.created_at else "",
        })

    return {"products": products, "total": len(products)}


async def _execute_get_product_detail(product_id: str) -> dict:
    try:
        uid = UUID(product_id)
    except ValueError:
        return {"found": False, "error": "ID sản phẩm không hợp lệ"}

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Listing)
            .options(selectinload(Listing.seller), selectinload(Listing.images))
            .where(Listing.id == uid)
        )
        item = result.scalar_one_or_none()

    if not item:
        return {"found": False, "error": "Không tìm thấy sản phẩm"}

    primary_img = next((img.image_url for img in (item.images or []) if img.is_primary), None)
    if not primary_img and item.images:
        primary_img = item.images[0].image_url

    return {
        "found": True,
        "product": {
            "id": str(item.id),
            "title": item.title,
            "price": float(item.price) if item.price else 0,
            "description": (item.description or "")[:500],
            "condition": item.condition_grade or "unknown",
            "location": item.location_summary or "",
            "seller": item.seller.full_name if item.seller else "Unknown",
            "image_url": primary_img,
            "created_at": item.created_at.isoformat() if item.created_at else "",
            "updated_at": item.updated_at.isoformat() if item.updated_at else "",
        },
    }


async def _execute_get_trending_products() -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Listing)
            .options(selectinload(Listing.seller), selectinload(Listing.images))
            .where(Listing.status == ListingStatus.ACTIVE, Listing.created_at >= cutoff)
            .order_by(Listing.view_count.desc())
            .limit(10)
        )
        items = result.scalars().all()

    products = []
    for item in items:
        primary_img = next((img.image_url for img in (item.images or []) if img.is_primary), None)
        if not primary_img and item.images:
            primary_img = item.images[0].image_url
        products.append({
            "id": str(item.id),
            "title": item.title,
            "price": float(item.price) if item.price else 0,
            "condition": item.condition_grade or "unknown",
            "location": item.location_summary or "",
            "views": item.view_count or 0,
            "seller": item.seller.full_name if item.seller else "Unknown",
            "image_url": primary_img,
        })

    return {"products": products, "total": len(products)}


def _generate_suggested_actions(products: list[dict], answer: str, has_faq: bool) -> list[dict]:
    actions = []

    # Actions based on found products
    if products:
        if len(products) > 1:
            actions.append({"label": f"🔍 Xem chi tiết sản phẩm đầu tiên", "payload": f"Xem thông tin sản phẩm {products[0]['id']}"})
            actions.append({"label": "📋 Xem tất cả sản phẩm", "payload": "Tìm sản phẩm tương tự"})
        else:
            actions.append({"label": "🔍 Xem chi tiết", "payload": f"Xem thông tin sản phẩm {products[0]['id']}"})
            actions.append({"label": "🔎 Tìm sản phẩm tương tự", "payload": f"Tìm sản phẩm giống {products[0]['title'][:50]}"})

    # FAQ-related actions
    if has_faq:
        actions.append({"label": "📖 Xem thêm câu hỏi", "payload": "Các câu hỏi thường gặp"})

    # General contextual actions
    answer_lower = answer.lower()
    if "iphone" in answer_lower or "samsung" in answer_lower or "laptop" in answer_lower:
        pass  # already have product actions
    elif "phí" in answer_lower or "escrow" in answer_lower or "thanh toán" in answer_lower:
        actions.append({"label": "💰 Hướng dẫn thanh toán", "payload": "Hướng dẫn thanh toán escrow"})
        actions.append({"label": "📦 Đăng tin bán hàng", "payload": "Làm thế nào để đăng tin bán hàng?"})

    # Deduplicate by payload
    seen = set()
    unique = []
    for a in actions:
        if a["payload"] not in seen:
            seen.add(a["payload"])
            unique.append(a)

    return unique[:4]  # max 4 actions


TOOL_DISPATCH = {
    "search_faq": lambda args: _execute_search_faq(args.get("query", "")),
    "search_products": lambda args: _execute_search_products(
        args.get("keyword", ""),
        min_price=args.get("min_price"),
        max_price=args.get("max_price"),
    ),
    "get_product_detail": lambda args: _execute_get_product_detail(args.get("product_id", "")),
    "get_trending_products": lambda _args: _execute_get_trending_products(),
}
