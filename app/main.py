from app.crud import crud_offer
from app.db.session import AsyncSessionLocal
from app.db.init_db import init_db
from app.core.config import settings
from app.api.main import api_router
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Create services directory on app startup (__init__.py is handled by backend_pre_start.py)
_services_dir = Path(__file__).parent / "services"
_services_dir.mkdir(parents=True, exist_ok=True)


logger = logging.getLogger(__name__)
offer_expiry_task: asyncio.Task | None = None

limiter = Limiter(key_func=get_remote_address)


async def _offer_expiry_worker() -> None:
    """Background worker to expire stale offers."""
    while True:
        try:
            async with AsyncSessionLocal() as session:
                expired_count = await crud_offer.expire_stale_offers(session)
                if expired_count:
                    logger.info("Expired %s stale offers", expired_count)
        except Exception:
            logger.exception("Offer expiry worker failed")

        await asyncio.sleep(settings.OFFER_EXPIRY_JOB_INTERVAL_MINUTES * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    global offer_expiry_task

    # Startup
    await init_db()
    offer_expiry_task = asyncio.create_task(_offer_expiry_worker())
    logger.info("Application started")

    yield

    # Shutdown
    if offer_expiry_task:
        offer_expiry_task.cancel()
        try:
            await offer_expiry_task
        except asyncio.CancelledError:
            pass
    logger.info("Application shutdown complete")


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# GZip compression for responses
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS - use explicit origins from config for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

# Serve uploaded files from local filesystem when not using MinIO
if not settings.use_minio:
    from fastapi.staticfiles import StaticFiles
    import os
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    app.mount(f"/{settings.UPLOAD_DIR}", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Add health check for Docker
utils_router = APIRouter(prefix="/utils", tags=["Utils"])


@utils_router.get("/health-check/")
async def health_check():
    return {"status": "ok"}

app.include_router(utils_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {"message": "Welcome to ReMarket API"}
