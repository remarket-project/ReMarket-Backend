"""
Wallet schemas for request/response validation.
"""
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

# ============================================================================
# Request Schemas
# ============================================================================

class WalletTopupRequest(BaseModel):
    """Request body for demo topup."""
    amount: Decimal = Field(
        ...,
        gt=Decimal("0"),
        le=Decimal("10000000"),
        decimal_places=2,
        description="Amount to add (max 10,000,000 VND)"
    )


# ============================================================================
# Response Schemas
# ============================================================================

class WalletRead(BaseModel):
    """Wallet information response."""
    id: uuid.UUID
    user_id: uuid.UUID
    balance: Decimal
    locked_balance: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TransactionRead(BaseModel):
    """Wallet transaction response."""
    id: uuid.UUID
    wallet_id: uuid.UUID
    amount: Decimal
    type: str
    description: str | None
    order_id: uuid.UUID | None
    escrow_id: uuid.UUID | None
    payment_gateway_ref: str | None = None
    bank_code: str | None = None
    bank_account: str | None = None
    status: str = "completed"
    balance_before: Decimal
    balance_after: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    """Paginated transaction list response."""
    transactions: list[TransactionRead]
    total: int
