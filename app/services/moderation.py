import base64
import json
import logging
import uuid
from datetime import datetime, timezone
from io import BytesIO

import httpx
from openai import AsyncOpenAI
from PIL import Image
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.enums import ListingStatus, NotificationType
from app.models.listing import Listing

logger = logging.getLogger(__name__)

MODERATION_PROMPT = """Moderate ReMarket listing (VN). Return JSON: {{"decision":"approve"|"flag"|"reject","reason":"brief VN ≤50 chars"}}
REJECT: weapons,drugs,alcohol,tobacco,hazard,counterfeit,NSFW,contact(phone/email/Zalo/social),services,digital goods,blurry/screenshot/watermark
FLAG: suspicious price,incomplete,borderline
APPROVE: genuine,clear,appropriate
Title:{title} Desc:{description} Cat:{category}"""


class ModerationResult:
    __slots__ = ("decision", "reason", "model_used")

    def __init__(self, decision: str, reason: str = "", model_used: str = ""):
        self.decision = decision      # "approve" | "flag" | "reject" | "error"
        self.reason = reason
        self.model_used = model_used


_nine_router_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _nine_router_client
    if _nine_router_client is None:
        _nine_router_client = AsyncOpenAI(
            base_url=settings.NINE_ROUTER_BASE_URL,
            api_key=settings.NINE_ROUTER_API_KEY or "sk-9router",
            timeout=httpx.Timeout(60.0, connect=5.0),
        )
    return _nine_router_client


MAX_IMAGE_DIM = 800
JPEG_QUALITY = 70


async def _image_to_base64(image_url: str) -> str:
    if image_url.startswith("/"):
        url = f"{settings.BACKEND_HOST.rstrip('/')}{image_url}"
    else:
        url = image_url

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    img = Image.open(BytesIO(resp.content))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    if img.width > MAX_IMAGE_DIM or img.height > MAX_IMAGE_DIM:
        ratio = MAX_IMAGE_DIM / max(img.width, img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"


async def moderate_listing(
    listing_id: str,
    title: str,
    description: str | None,
    category_name: str,
    image_urls: list[str] | None = None,
) -> ModerationResult:
    if not settings.NINE_ROUTER_BASE_URL:
        return ModerationResult("flag", "AI moderation not configured")

    prompt = MODERATION_PROMPT.format(
        title=title[:500],
        description=(description or "")[:2000],
        category=category_name or "Unknown",
    )

    content_parts: list[dict] = [{"type": "text", "text": prompt}]

    if image_urls:
        for url in image_urls:
            try:
                b64 = await _image_to_base64(url)
                content_parts.append({"type": "image_url", "image_url": {"url": b64}})
            except Exception as e:
                logger.warning("Failed to download image %s: %s", url[:50], e)

    last_error: Exception | None = None
    for model in settings.AI_MODERATION_MODELS:
        try:
            response = await _get_client().chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": content_parts},
                ],
                response_format={"type": "json_object"},
                max_tokens=120,
                temperature=0.1,
            )
            raw = response.choices[0].message.content
            result = _parse_response(raw)
            if result:
                result.model_used = model
                logger.info("Moderation: %s (model=%s)", result.decision, model)
                return result
        except Exception as e:
            last_error = e
            logger.warning("Model %s failed: %s — trying next", model, str(e)[:100])
            continue

    logger.error("All moderation models exhausted: %s", last_error)
    return ModerationResult("flag", "AI moderation unavailable")


def _parse_response(raw: str | None) -> ModerationResult | None:
    if not raw:
        return None
    try:
        cleaned = raw.strip()
        cleaned = cleaned.removeprefix("```json").removeprefix("```")
        cleaned = cleaned.removesuffix("```").strip()
        data = json.loads(cleaned)
        decision = data.get("decision", "flag")
        reason = data.get("reason", "")
        if decision not in ("approve", "flag", "reject"):
            decision = "flag"
        return ModerationResult(decision=decision, reason=reason)
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to parse moderation response: %s", e)
        return None


def _to_uuid(value: str | uuid.UUID) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(value)


async def apply_moderation_result(
    listing_id: str,
    result: ModerationResult,
):
    from app.core.websocket_manager import ws_manager
    from app.crud import crud_notification, crud_user

    async with AsyncSessionLocal() as db:
        listing_result = await db.execute(
            select(Listing)
            .options(joinedload(Listing.seller), joinedload(Listing.category))
            .where(Listing.id == _to_uuid(listing_id))
        )
        listing = listing_result.unique().scalar_one_or_none()
        if not listing:
            logger.warning("Listing %s not found", listing_id)
            return

        admin_ids = await crud_user.get_admin_user_ids(db)

        if result.decision == "approve":
            listing.status = ListingStatus.ACTIVE
            listing.rejection_reason = None
            listing.updated_at = datetime.now(timezone.utc)
            db.add(listing)
            await db.commit()

            await crud_notification.create_notification(
                db=db, user_id=listing.seller_id,
                type=NotificationType.LISTING_APPROVED,
                title="Bài đăng được duyệt tự động",
                message=f"AI đã duyệt bài đăng '{listing.title}'.",
                data={"listing_id": listing_id},
            )
            await ws_manager.send_to_user(
                listing.seller_id,
                {"type": "listing_approved", "listing_id": listing_id},
            )
            await ws_manager.broadcast_to_all(
                {"type": "listing_approved_broadcast", "listing_id": listing_id},
            )

        elif result.decision == "reject":
            listing.status = ListingStatus.REJECTED
            listing.rejection_reason = result.reason
            listing.updated_at = datetime.now(timezone.utc)
            db.add(listing)
            await db.commit()

            await crud_notification.create_notification(
                db=db, user_id=listing.seller_id,
                type=NotificationType.LISTING_REJECTED,
                title="Bài đăng bị từ chối",
                message=f"Bài đăng vi phạm quy định: {result.reason}",
                data={"listing_id": listing_id, "reason": result.reason},
            )
            await ws_manager.send_to_user(
                listing.seller_id,
                {"type": "listing_rejected", "listing_id": listing_id},
            )
            if admin_ids:
                await ws_manager.broadcast_to_users(
                    admin_ids,
                    {"type": "listing_rejected_broadcast", "listing_id": listing_id},
                )

        else:  # "flag" hoặc "error"
            listing.rejection_reason = result.reason
            listing.updated_at = datetime.now(timezone.utc)
            db.add(listing)
            await db.commit()

        # Cập nhật real-time cho admin audit log
        if admin_ids:
            await ws_manager.broadcast_to_users(
                admin_ids, {"type": "new_moderation_log"},
            )


async def run_moderation(
    listing_id: str,
    title: str,
    description: str | None,
    category_name: str,
    image_urls: list[str] | None = None,
):
    from app.crud import crud_moderation_log

    result = await moderate_listing(
        listing_id=listing_id,
        title=title,
        description=description,
        category_name=category_name,
        image_urls=image_urls,
    )
    await apply_moderation_result(listing_id, result)

    async with AsyncSessionLocal() as db:
        await crud_moderation_log.create_moderation_log(
            db=db,
            listing_id=_to_uuid(listing_id),
            listing_title=title[:500],
            decision=result.decision,
            reason=result.reason,
            model_used=result.model_used,
            image_count=len(image_urls) if image_urls else 0,
        )
