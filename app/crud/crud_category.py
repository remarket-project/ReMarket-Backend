"""
CRUD operations for Category model.

Pure database operations (no business logic).
"""
import uuid

from sqlmodel import Session, select

from app.models import Category, CategoryCreate, CategoryUpdate


async def get_category_by_id(db: Session, category_id: uuid.UUID) -> Category | None:
    """Get category by ID."""
    return db.get(Category, category_id)


async def get_category_by_slug(db: Session, slug: str) -> Category | None:
    """Get category by slug."""
    statement = select(Category).where(Category.slug == slug)
    return db.exec(statement).first()


async def get_categories_root(db: Session) -> list[Category]:
    """Get all root categories (parent_id is None)."""
    statement = select(Category).where(Category.parent_id.is_(None))
    return db.exec(statement).all()


async def get_categories_by_parent(db: Session, parent_id: uuid.UUID) -> list[Category]:
    """Get all categories with given parent_id."""
    statement = select(Category).where(Category.parent_id == parent_id)
    return db.exec(statement).all()


async def get_all_categories(db: Session, skip: int = 0, limit: int = 100) -> list[Category]:
    """Get all categories with pagination."""
    statement = select(Category).offset(skip).limit(limit)
    return db.exec(statement).all()


async def create_category(db: Session, category_in: CategoryCreate) -> Category:
    """Create a new category."""
    category = Category(
        name=category_in.name,
        slug=category_in.slug,
        icon_url=category_in.icon_url,
        parent_id=category_in.parent_id
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


async def update_category(
    db: Session, category: Category, category_in: CategoryUpdate
) -> Category:
    """Update existing category."""
    update_data = category_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(category, field) and value is not None:
            setattr(category, field, value)

    db.add(category)
    db.commit()
    db.refresh(category)
    return category


async def delete_category(db: Session, category_id: uuid.UUID) -> bool:
    """Delete category by ID. Returns True if deleted."""
    category = await get_category_by_id(db, category_id)
    if category:
        db.delete(category)
        db.commit()
        return True
    return False


async def get_categories_count(db: Session) -> int:
    """Get total count of categories."""
    statement = select(Category)
    return len(db.exec(statement).all())
