"""
Database session configuration with async support and connection pooling.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

# Production-ready engine configuration with connection pooling
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,  # Configurable, default False in prod
    future=True,
    pool_size=settings.DB_POOL_SIZE,  # Default: 20
    max_overflow=settings.DB_MAX_OVERFLOW,  # Default: 10
    pool_timeout=settings.DB_POOL_TIMEOUT,  # Default: 30 seconds
    pool_recycle=settings.DB_POOL_RECYCLE,  # Default: 1800 (30 min)
    pool_pre_ping=True,  # Verify connections before use
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
    autoflush=False,  # Better control over when to flush
)


async def get_db():
    """Get database session for dependency injection."""
    async with AsyncSessionLocal() as session:
        yield session
