"""Re-index all listings with proper error handling."""
import asyncio
import logging
import sys

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.core.ai_client import ai_client
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.listing import Listing, ListingStatus
from app.models.faq import FaqChunk
from app.services.faq_indexer import index_faq
from app.services.embeddings import embed_listing_full

logging.basicConfig(level=logging.INFO, stream=sys.stdout, force=True)
logger = logging.getLogger(__name__)


async def check_model():
    logger.info("=" * 60)
    logger.info(f"Model: {settings.LOCAL_EMBED_MODEL}")
    logger.info(f"Embed dim: {settings.AI_EMBED_DIM}")
    test_vec = await ai_client.embed_one("test product", prefix="query: ")
    logger.info(f"Test embedding dim: {len(test_vec)}")
    logger.info("=" * 60)


async def reindex_listings():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Listing).options(selectinload(Listing.seller))
            .where(Listing.status == ListingStatus.ACTIVE)
        )
        listings = list(result.scalars().all())

    logger.info(f"Found {len(listings)} active listings")

    success = 0
    failed = 0
    for i, listing in enumerate(listings):
        title = (listing.title or "")[:40]
        try:
            vec = await embed_listing_full(listing)
            if vec and len(vec) == 768:
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        update(Listing).where(Listing.id == listing.id).values(embedding=vec)
                    )
                    await db.commit()
                success += 1
                if (i + 1) % 20 == 0:
                    logger.info(f"  [{i+1}/{len(listings)}] ... {success} OK, {failed} failed")
            elif vec:
                logger.warning(f"  [{i+1}/{len(listings)}] {title}... wrong dim: {len(vec)}")
                failed += 1
            else:
                logger.info(f"  [{i+1}/{len(listings)}] {title}... SKIP (empty)")
        except Exception as e:
            logger.error(f"  [{i+1}/{len(listings)}] {title}... FAILED: {e}")
            failed += 1

    logger.info(f"Done! {success} OK, {failed} failed")


async def main():
    await check_model()
    await reindex_listings()
    logger.info("Now re-indexing FAQ chunks...")
    await index_faq()
    logger.info("All done!")


if __name__ == "__main__":
    asyncio.run(main())
