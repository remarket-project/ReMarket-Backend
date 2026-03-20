from fastapi import APIRouter

from app.api.routes import auth, categories_route, users_route
from app.core.config import settings

api_router = APIRouter()

# ============================================================================
# Sprint 1 Routes (Auth + Users + Categories)
# ============================================================================
api_router.include_router(auth.router)
api_router.include_router(users_route.router)
api_router.include_router(categories_route.router)
