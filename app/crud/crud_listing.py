"""
CRUD operations for Listing model.

Handles listing creation, retrieval, updates, and searches with image handling.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from app.models.enums import ListingStatus
from app.models.listing import Listing, ListingImage


def _to_uuid(value: str | uuid.UUID) -> uuid.UUID:
    """Convert string or UUID to UUID."""
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


async def create_listing(
    db: AsyncSession,
    title: str,
    description: Optional[str],
    price,
    is_negotiable: bool,
    condition_grade,
    seller_id: str,
    category_id: str
) -> Listing:
    """Create a new listing."""
    db_obj = Listing(
        title=title,
        description=description,
        price=price,
        is_negotiable=is_negotiable,
        condition_grade=condition_grade,
        seller_id=uuid.UUID(seller_id),
        category_id=uuid.UUID(category_id),
        status=ListingStatus.PENDING
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def get_listing(db: AsyncSession, listing_id: str) -> Optional[Listing]:
    """Get listing by ID."""
    result = await db.execute(
        select(Listing).options(joinedload(Listing.seller)).where(Listing.id == _to_uuid(listing_id))
    )
    return result.scalar_one_or_none()


async def get_listing_images(
    db: AsyncSession,
    listing_id: str
) -> list[ListingImage]:
    """Get all images for a listing."""
    result = await db.execute(
        select(ListingImage).where(
            ListingImage.listing_id == _to_uuid(listing_id))
    )
    return list(result.scalars().all())


async def get_images_for_listings(
    db: AsyncSession,
    listing_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[ListingImage]]:
    """
    Batch load images for multiple listings in a single query.
    Fixes N+1 query problem.
    """
    if not listing_ids:
        return {}

    result = await db.execute(
        select(ListingImage)
        .where(ListingImage.listing_id.in_(listing_ids))
        .order_by(ListingImage.listing_id, ListingImage.is_primary.desc())
    )
    images = result.scalars().all()

    # Group images by listing_id
    images_by_listing: dict[uuid.UUID, list[ListingImage]] = {}
    for img in images:
        if img.listing_id not in images_by_listing:
            images_by_listing[img.listing_id] = []
        images_by_listing[img.listing_id].append(img)

    return images_by_listing


async def add_listing_image(
    db: AsyncSession,
    listing_id: str,
    image_url: str,
    is_primary: bool = False
) -> ListingImage:
    """Add an image to a listing."""
    # If this is primary, unset other primary images
    if is_primary:
        await db.execute(
            update(ListingImage)
            .where(ListingImage.listing_id == _to_uuid(listing_id))
            .values(is_primary=False)
        )

    db_img = ListingImage(
        listing_id=uuid.UUID(listing_id),
        image_url=image_url,
        is_primary=is_primary
    )
    db.add(db_img)
    await db.commit()
    await db.refresh(db_img)
    return db_img


async def update_listing(
    db: AsyncSession,
    listing_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    price=None,
    is_negotiable: Optional[bool] = None,
    condition_grade=None,
) -> Optional[Listing]:
    """Update a listing (partial update)."""
    update_data = {}
    if title is not None:
        update_data["title"] = title
    if description is not None:
        update_data["description"] = description
    if price is not None:
        update_data["price"] = price
    if is_negotiable is not None:
        update_data["is_negotiable"] = is_negotiable
    if condition_grade is not None:
        update_data["condition_grade"] = condition_grade

    if not update_data:
        return await get_listing(db, listing_id)

    update_data["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None)

    await db.execute(
        update(Listing)
        .where(Listing.id == _to_uuid(listing_id))
        .values(**update_data)
    )
    await db.commit()
    return await get_listing(db, listing_id)


async def update_listing_status(
    db: AsyncSession,
    listing_id: str,
    status: ListingStatus
) -> Optional[Listing]:
    """Update listing status."""
    await db.execute(
        update(Listing)
        .where(Listing.id == _to_uuid(listing_id))
        .values(status=status, updated_at=datetime.now(timezone.utc).replace(tzinfo=None))
    )
    await db.commit()
    return await get_listing(db, listing_id)


async def soft_delete_listing(db: AsyncSession, listing_id: str) -> None:
    """Soft delete a listing by marking as HIDDEN."""
    await db.execute(
        update(Listing)
        .where(Listing.id == _to_uuid(listing_id))
        .values(
            status=ListingStatus.HIDDEN,
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
    )
    await db.commit()


async def search_listings(
    db: AsyncSession,
    keyword: Optional[str] = None,
    category_id: Optional[str] = None,
    seller_id: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    status: Optional[ListingStatus] = ListingStatus.ACTIVE,
    sort_by: str = "newest",
    featured_only: bool = False,
    skip: int = 0,
    limit: int = 100
) -> tuple[list[Listing], int]:
    """Search listings with filters."""
    query = select(Listing).options(joinedload(Listing.seller))
    count_query = select(func.count()).select_from(Listing)

    conditions = []

    if status:
        conditions.append(Listing.status == status)
    if featured_only:
        conditions.append(Listing.is_featured.is_(True))
    if keyword:
        keyword_filter = f"%{keyword}%"
        conditions.append(
            or_(
                Listing.title.ilike(keyword_filter),
                Listing.description.ilike(keyword_filter),
                Listing.location_summary.ilike(keyword_filter),
            )
        )
    if category_id:
        conditions.append(Listing.category_id == _to_uuid(category_id))
    if seller_id:
        conditions.append(Listing.seller_id == _to_uuid(seller_id))
    if min_price is not None:
        conditions.append(Listing.price >= min_price)
    if max_price is not None:
        conditions.append(Listing.price <= max_price)

    if conditions:
        for condition in conditions:
            query = query.where(condition)
            count_query = count_query.where(condition)

    # Count total
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Get paginated results
    order_map = {
        "newest": [Listing.created_at.desc()],
        "oldest": [Listing.created_at.asc()],
        "price_asc": [Listing.price.asc(), Listing.created_at.desc()],
        "price_desc": [Listing.price.desc(), Listing.created_at.desc()],
        "popular": [Listing.view_count.desc(), Listing.save_count.desc(), Listing.created_at.desc()],
        "featured": [Listing.is_featured.desc(), Listing.published_at.desc(), Listing.created_at.desc()],
    }
    query = query.order_by(
        *order_map.get(sort_by, order_map["newest"])).offset(skip).limit(limit)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total


async def get_featured_listings(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Listing], int]:
    return await search_listings(
        db,
        status=ListingStatus.ACTIVE,
        sort_by="featured",
        featured_only=True,
        skip=skip,
        limit=limit,
    )


async def get_related_listings(
    db: AsyncSession,
    listing: Listing,
    skip: int = 0,
    limit: int = 8,
) -> tuple[list[Listing], int]:
    count_result = await db.execute(
        select(func.count()).select_from(Listing).where(
            Listing.status == ListingStatus.ACTIVE,
            Listing.id != listing.id,
            Listing.category_id == listing.category_id,
        )
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(Listing)
        .options(joinedload(Listing.seller))
        .where(
            Listing.status == ListingStatus.ACTIVE,
            Listing.id != listing.id,
            Listing.category_id == listing.category_id,
        )
        .order_by(
            Listing.is_featured.desc(),
            Listing.view_count.desc(),
            Listing.created_at.desc(),
        )
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all()), int(total)


async def get_listing_suggestions(
    db: AsyncSession,
    keyword: str,
    limit: int = 10,
) -> list[str]:
    result = await db.execute(
        select(Listing.title)
        .where(
            Listing.status == ListingStatus.ACTIVE,
            Listing.title.ilike(f"%{keyword}%"),
        )
        .order_by(Listing.view_count.desc(), Listing.created_at.desc())
        .limit(limit)
    )
    return [row[0] for row in result.all() if row[0]]


async def get_price_band_summary(
    db: AsyncSession,
    category_id: Optional[str] = None,
) -> list[dict[str, object]]:
    bands = [
        {"label": "Dưới 1 triệu", "min_price": 0, "max_price": 1_000_000},
        {"label": "1 - 3 triệu", "min_price": 1_000_000, "max_price": 3_000_000},
        {"label": "3 - 5 triệu", "min_price": 3_000_000, "max_price": 5_000_000},
        {"label": "5 - 10 triệu", "min_price": 5_000_000, "max_price": 10_000_000},
        {"label": "Trên 10 triệu", "min_price": 10_000_000, "max_price": None},
    ]

    base_filters = [Listing.status == ListingStatus.ACTIVE]
    if category_id:
        base_filters.append(Listing.category_id == _to_uuid(category_id))

    summary: list[dict[str, object]] = []
    for band in bands:
        band_filters = list(base_filters)
        if band["min_price"] is not None:
            band_filters.append(Listing.price >= band["min_price"])
        if band["max_price"] is not None:
            band_filters.append(Listing.price < band["max_price"])

        count_result = await db.execute(
            select(func.count()).select_from(Listing).where(*band_filters)
        )
        summary.append({
            **band,
            "count": int(count_result.scalar_one()),
        })

    return summary


async def get_listing_image(
    db: AsyncSession,
    image_id: str
) -> Optional[ListingImage]:
    """Get image by ID."""
    result = await db.execute(
        select(ListingImage).where(ListingImage.id == _to_uuid(image_id))
    )
    return result.scalar_one_or_none()


async def delete_listing_image(db: AsyncSession, image_id: str) -> None:
    """Delete an image."""
    await db.execute(
        delete(ListingImage).where(ListingImage.id == _to_uuid(image_id))
    )
    await db.commit()


async def get_pending_listings(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100
) -> list[Listing]:
    """Get all pending listings (for admin approval)."""
    result = await db.execute(
        select(Listing)
        .where(Listing.status == ListingStatus.PENDING)
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())
