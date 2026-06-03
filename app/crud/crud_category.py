"""
CRUD operations for Category model.

Pure database operations (no business logic).
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models import Category, CategoryCreate, CategoryUpdate


async def get_category_by_id(
    db: AsyncSession,
    category_id: uuid.UUID
) -> Category | None:
    """Get category by ID."""
    result = await db.execute(select(Category).where(Category.id == category_id))
    return result.scalar_one_or_none()


async def get_category_by_slug(
    db: AsyncSession,
    slug: str
) -> Category | None:
    """Get category by slug."""
    result = await db.execute(select(Category).where(Category.slug == slug))
    return result.scalar_one_or_none()


async def get_all_categories(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100
) -> list[Category]:
    """Get all categories with pagination."""
    result = await db.execute(
        select(Category).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def create_category(
    db: AsyncSession,
    category_in: CategoryCreate
) -> Category:
    """Create a new category."""
    category = Category(
        name=category_in.name,
        slug=category_in.slug,
        icon_url=category_in.icon_url,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


async def update_category(
    db: AsyncSession,
    category_id: uuid.UUID,
    category_in: CategoryUpdate
) -> Category | None:
    """Update existing category."""
    category = await get_category_by_id(db, category_id)
    if not category:
        return None

    update_data = category_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(category, field) and value is not None:
            setattr(category, field, value)

    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


async def delete_category(db: AsyncSession, category_id: uuid.UUID) -> bool:
    """Delete category by ID. Returns True if deleted."""
    category = await get_category_by_id(db, category_id)
    if category:
        await db.delete(category)
        await db.commit()
        return True
    return False


async def get_categories_count(db: AsyncSession) -> int:
    """Get total count of categories."""
    from sqlalchemy import func
    result = await db.execute(select(func.count()).select_from(Category))
    return result.scalar_one()
