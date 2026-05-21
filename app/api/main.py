from fastapi import APIRouter

from app.api.routes import (
    auth,
    categories_route,
    users_route,
    listings,
    offers,
    orders,
    reviews,
    admin,
    notifications,
    content,
    websocket,
    wallet,
    escrow,
)
from app.core.config import settings

api_router = APIRouter()

# ============================================================================
# Sprint 1 Routes (Auth + Users + Categories)
# ============================================================================
api_router.include_router(auth.router)
api_router.include_router(users_route.router)
api_router.include_router(categories_route.router)

# ============================================================================
# Sprint 2 Routes (Listings + Offers + Orders + Reviews + Admin + Notifications)
# ============================================================================
api_router.include_router(listings.router)
api_router.include_router(offers.router)
api_router.include_router(orders.router)
api_router.include_router(reviews.router)
api_router.include_router(admin.router)
api_router.include_router(notifications.router)
api_router.include_router(content.router)

# ============================================================================
# Wallet Route
# ============================================================================
api_router.include_router(wallet.router)

# ============================================================================
# Escrow Route
# ============================================================================
api_router.include_router(escrow.router)

# ============================================================================
# WebSocket Route
# ============================================================================
api_router.include_router(websocket.router)
