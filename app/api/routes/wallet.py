"""
Wallet API endpoints.

Handles wallet management, balance viewing, and transaction history.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import CurrentUser, SessionDep
from app.crud import crud_wallet
from app.models.enums import TransactionType
from app.schemas.wallet import (
    WalletRead,
    WalletTopupRequest,
    TransactionRead,
    TransactionListResponse
)

router = APIRouter(prefix="/wallet", tags=["Wallet"])
limiter = Limiter(key_func=get_remote_address)


# ============================================================================
# Get My Wallet
# ============================================================================

@router.get("/me", response_model=WalletRead)
async def get_my_wallet(
    current_user: CurrentUser,
    db: SessionDep
) -> WalletRead:
    """
    Get my wallet information.

    Auto-creates wallet if it doesn't exist.

    **Response:**
    - Wallet with balance and locked_balance

    **Errors:**
    - 401: Unauthorized
    """
    wallet = await crud_wallet.get_or_create_wallet(db, current_user.id)
    return wallet


# ============================================================================
# Demo Topup
# ============================================================================

@router.post("/demo-topup", response_model=WalletRead)
@limiter.limit("10/hour")
async def demo_topup(
    request: Request,
    current_user: CurrentUser,
    db: SessionDep,
    data: WalletTopupRequest
) -> WalletRead:
    """
    Demo: Add funds to wallet (for testing purposes).

    **Request body:**
    - amount: Amount to add (max 10,000,000 VND)

    **Response:**
    - Updated wallet

    **Errors:**
    - 400: Invalid amount
    - 401: Unauthorized
    - 429: Rate limit exceeded
    """
    # Get or create wallet
    wallet = await crud_wallet.get_or_create_wallet(db, current_user.id)

    # Add balance
    try:
        updated_wallet, transaction = await crud_wallet.add_balance(
            db=db,
            wallet_id=wallet.id,
            amount=data.amount,
            transaction_type=TransactionType.DEPOSIT,
            description=f"Demo topup: {data.amount:,.0f} VND"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return updated_wallet


# ============================================================================
# Get Transaction History
# ============================================================================

@router.get("/transactions", response_model=TransactionListResponse)
async def get_transactions(
    current_user: CurrentUser,
    db: SessionDep,
    skip: int = 0,
    limit: int = 20
) -> TransactionListResponse:
    """
    Get wallet transaction history.

    **Query parameters:**
    - skip: Number of records to skip (default: 0)
    - limit: Maximum records to return (default: 20, max: 100)

    **Response:**
    - List of transactions and total count

    **Errors:**
    - 401: Unauthorized
    """
    # Validate limit
    if limit > 100:
        limit = 100

    # Get or create wallet
    wallet = await crud_wallet.get_or_create_wallet(db, current_user.id)

    # Get transactions
    transactions, total = await crud_wallet.get_wallet_transactions(
        db=db,
        wallet_id=wallet.id,
        skip=skip,
        limit=limit
    )

    return TransactionListResponse(
        transactions=transactions,
        total=total
    )
