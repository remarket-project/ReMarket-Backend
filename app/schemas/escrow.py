"""
Escrow schemas for request/response validation.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

# ============================================================================
# Request Schemas
# ============================================================================

class OpenDisputeRequest(BaseModel):
    """Request body for opening a dispute."""
    reason: str = Field(..., min_length=10, max_length=500,
                        description="Reason for dispute")


class ResolveEscrowRequest(BaseModel):
    """Admin resolution for disputed escrow."""
    result: Literal["release", "refund"] = Field(
        ...,
        description="release: transfer to seller, refund: return funds to buyer"
    )
    note: str | None = Field(
        default=None,
        max_length=500,
        description="Optional admin note"
    )


# ============================================================================
# Response Schemas
# ============================================================================

class EscrowRead(BaseModel):
    """Escrow information response (simplified)."""
    id: uuid.UUID
    order_id: uuid.UUID
    amount: Decimal
    status: str
    buyer_wallet_id: uuid.UUID
    seller_wallet_id: uuid.UUID
    funded_at: datetime | None
    released_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
