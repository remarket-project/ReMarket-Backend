import asyncio
import json
import logging
from pathlib import Path

from app.core.ai_client import ai_client
from app.db.session import AsyncSessionLocal
from app.models.faq import FaqChunk
from app.services.faq_cache import faq_cache

logger = logging.getLogger(__name__)

FAQ_DATA_PATH = Path(__file__).resolve().parent / "faq_data.json"


async def index_faq():
    if not FAQ_DATA_PATH.exists():
        logger.error("faq_data.json not found at %s", FAQ_DATA_PATH)
        return 0

    with open(FAQ_DATA_PATH, encoding="utf-8") as f:
        items = json.load(f)

    async with AsyncSessionLocal() as db:
        await db.execute(FaqChunk.__table__.delete())
        await db.commit()

        for item in items:
            text = f"{item['q']} {item['a']}"
            embeddings = await ai_client.embed([text], prefix="passage: ")
            if embeddings:
                db.add(FaqChunk(
                    question=item["q"],
                    answer=item["a"],
                    embedding=embeddings[0],
                ))

        await db.commit()

    faq_cache.clear()
    logger.info("Indexed %d FAQ items (cache cleared)", len(items))
    return len(items)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(index_faq())
