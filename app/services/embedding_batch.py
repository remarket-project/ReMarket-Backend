import asyncio
import logging

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.listing import Listing
from app.services.embeddings import embed_listing_full

logger = logging.getLogger(__name__)


async def batch_embed_all_listings(batch_size: int = 50):
    total_processed = 0
    async with AsyncSessionLocal() as db:
        while True:
            result = await db.execute(
                select(Listing)
                .where(Listing.embedding.is_(None))  # type: ignore[attr-defined]
                .limit(batch_size)
            )
            listings = list(result.scalars().all())
            if not listings:
                break

            for listing in listings:
                try:
                    listing.embedding = await embed_listing_full(listing)
                    db.add(listing)
                    total_processed += 1
                except Exception as e:
                    logger.error("Embed failed for listing %s: %s", listing.id, e)

            await db.commit()
            logger.info("Embedded batch: %d listings (total: %d)", len(listings), total_processed)

    logger.info("Batch embedding complete. Total: %d", total_processed)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(batch_embed_all_listings())
