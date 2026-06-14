import logging

from app.core.ai_client import ai_client

logger = logging.getLogger(__name__)

EMBED_DIM = 384


async def embed_listing_text(text: str) -> list[float]:
    if not text or not text.strip():
        return []
    embeddings = await ai_client.embed([text.strip()], prefix="query: ")
    return embeddings[0] if embeddings else []


async def embed_listing_full(listing) -> list[float]:
    parts = [
        listing.title or "",
        listing.description or "",
    ]
    text = " ".join(p for p in parts if p).strip()
    if not text:
        return []
    embeddings = await ai_client.embed([text], prefix="passage: ")
    return embeddings[0] if embeddings else []
