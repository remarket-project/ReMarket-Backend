"""
Wallet API endpoints.

Handles wallet management, balance viewing, transaction history,
and Stripe Payout withdrawals (for sellers with connected accounts).
"""
from datetime import datetime, timezone
from decimal import Decimal

import sqlalchemy
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.crud import crud_wallet
from app.models.enums import TransactionType
from app.models.wallet import Wallet, WalletTransaction
from app.schemas.wallet import TransactionListResponse, WalletRead, WalletTopupRequest
from app.services import stripe_connect

router = APIRouter(prefix="/wallet", tags=["Wallet"])
limiter = Limiter(key_func=get_remote_address)


class WithdrawRequest(BaseModel):
    amount: Decimal = Field(..., gt=Decimal(0), decimal_places=2)


class WithdrawResponse(BaseModel):
    id: str
    amount: Decimal
    status: str
    message: str


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
    """
    wallet = await crud_wallet.get_or_create_wallet(db, current_user.id)
    return WalletRead.model_validate(wallet)


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
    """
    wallet = await crud_wallet.get_or_create_wallet(db, current_user.id)

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
        ) from e

    return WalletRead.model_validate(updated_wallet)


# ============================================================================
# Withdraw (Rút tiền — Stripe Payout)
# ============================================================================

@router.post("/withdraw", response_model=WithdrawResponse)
@limiter.limit("5/day")
async def withdraw(
    request: Request,
    current_user: CurrentUser,
    db: SessionDep,
    data: WithdrawRequest,
):
    """Yêu cầu rút tiền từ ví về tài khoản ngân hàng (Stripe Payout).

    Yêu cầu người dùng đã hoàn tất Stripe Connect onboarding.
    Số tiền được gửi trực tiếp qua Stripe Payouts API đến tài khoản ngân hàng
    đã đăng ký trong Stripe.
    """
    if not current_user.stripe_account_id or not current_user.stripe_onboarding_complete:
        raise HTTPException(
            status_code=400,
            detail="Bạn cần hoàn tất Stripe Connect onboarding trước khi rút tiền. "
                   "Vào Cài đặt > Thanh toán để bắt đầu.",
        )

    if data.amount < settings.WITHDRAW_MIN_AMOUNT:
        raise HTTPException(status_code=400, detail=f"Số tiền rút tối thiểu {settings.WITHDRAW_MIN_AMOUNT:,} VND")
    if data.amount > settings.WITHDRAW_MAX_AMOUNT:
        raise HTTPException(status_code=400, detail=f"Số tiền rút tối đa {settings.WITHDRAW_MAX_AMOUNT:,} VND")

    wallet = await crud_wallet.get_or_create_wallet(db, current_user.id)
    if wallet.balance < data.amount:
        raise HTTPException(status_code=400, detail="Số dư không đủ")

    result = await db.execute(
        sqlalchemy.select(Wallet)
        .where(Wallet.id == wallet.id)  # type: ignore[arg-type]
        .with_for_update(nowait=False)
    )
    locked_wallet = result.scalar_one_or_none()
    if not locked_wallet or locked_wallet.balance < data.amount:
        raise HTTPException(status_code=400, detail="Số dư không đủ")

    transfer = await stripe_connect.transfer_to_connected_account(
        amount_vnd=data.amount,
        destination_account_id=current_user.stripe_account_id,
        order_id=str(current_user.id),
        description=f"Wallet withdrawal: {data.amount:,.0f} VND",
    )

    balance_before = locked_wallet.balance
    locked_wallet.balance -= data.amount
    locked_wallet.updated_at = datetime.now(timezone.utc)

    tx = WalletTransaction(
        wallet_id=wallet.id,
        amount=-data.amount,
        type=TransactionType.WITHDRAW_PENDING.value,
        description=f"Rút tiền: {data.amount:,.0f} VND qua Stripe",
        balance_before=balance_before,
        balance_after=locked_wallet.balance,
        payment_gateway_ref=transfer["transfer_id"],
        stripe_transfer_id=transfer["transfer_id"],
        status="pending",
    )
    db.add(locked_wallet)
    db.add(tx)
    await db.commit()
    await db.refresh(tx)

    return WithdrawResponse(
        id=str(tx.id),
        amount=data.amount,
        status=transfer["status"],
        message="Yêu cầu rút tiền đã được gửi. "
                "Tiền đã chuyển vào tài khoản Stripe của bạn, "
                "vui lòng vào Stripe Express Dashboard để rút về ngân hàng.",
    )


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
    """
    if limit > 100:
        limit = 100

    wallet = await crud_wallet.get_or_create_wallet(db, current_user.id)

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
