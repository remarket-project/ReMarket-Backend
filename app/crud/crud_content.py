"""CRUD for static content pages."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.static_content import StaticContent


async def get_content_by_key(
    db: AsyncSession,
    key: str,
    locale: str = "vi",
) -> StaticContent | None:
    result = await db.execute(
        select(StaticContent).where(
            StaticContent.key == key,
            StaticContent.locale == locale,
        )
    )
    return result.scalar_one_or_none()


async def get_contents_by_keys(
    db: AsyncSession,
    keys: list[str],
    locale: str = "vi",
) -> list[StaticContent]:
    if not keys:
        return []

    result = await db.execute(
        select(StaticContent).where(
            StaticContent.locale == locale,
            StaticContent.key.in_(keys),
        )
    )
    contents = list(result.scalars().all())
    content_map = {content.key: content for content in contents}
    return [content_map[key] for key in keys if key in content_map]
