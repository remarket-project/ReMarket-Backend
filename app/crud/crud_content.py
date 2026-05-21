"""CRUD for static content pages."""
import uuid
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.static_content import StaticContent


async def get_content_by_key(db: AsyncSession, key: str, locale: str = "vi") -> StaticContent | None:
    result = await db.execute(select(StaticContent).where(StaticContent.key == key, StaticContent.locale == locale))
    return result.scalar_one_or_none()
