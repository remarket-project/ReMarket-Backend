"""
Database initialization module.

Creates all tables on startup.
"""
from sqlmodel import SQLModel
from app.db.session import engine

# Ensure model metadata is registered before create_all runs
import app.models.category  # noqa: F401
import app.models.listing  # noqa: F401
import app.models.notification  # noqa: F401
import app.models.offer  # noqa: F401
import app.models.order  # noqa: F401
import app.models.review  # noqa: F401
import app.models.user  # noqa: F401


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
