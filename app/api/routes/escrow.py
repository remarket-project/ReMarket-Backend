"""
Escrow API endpoints (simplified).

Only keeps GET (read-only) for escrow info.
Fund/release/dispute handling moved to orders + disputes routes.
"""
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, SessionDep
from app.crud import crud_escrow, crud_order
from app.models.enums import OrderStatus
from app.schemas.escrow import EscrowRead

router = APIRouter(prefix="/escrows", tags=["Escrow"])


@router.get("/{order_id:uuid}", response_model=EscrowRead)
async def get_escrow(
    order_id: uuid.UUID,
    current_user: CurrentUser,
    db: SessionDep
) -> Any:
    """
    Get escrow details for an order (read-only).

    Both buyer and seller can view escrow info.
    """
    escrow = await crud_escrow.get_escrow_by_order_id(db, order_id)
    if not escrow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escrow not found"
        )

    # Check authorization (buyer or seller)
    order = await crud_order.get_order_by_id(db, order_id)
    if not order or (order.buyer_id != current_user.id and order.seller_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this escrow"
        )

    return escrow
