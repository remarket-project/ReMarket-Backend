"""Payment API endpoints — Stripe deposit and webhook handling.

Replaces VNPay with Stripe PaymentIntents for wallet topup.
"""
import logging
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, SessionDep
from app.crud import crud_wallet
from app.models.enums import TransactionType
from app.models.wallet import WalletTransaction
from app.services import stripe_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payment", tags=["Payment"])


# ============================================================================
# Request / Response schemas
# ============================================================================


class DepositRequest(BaseModel):
    amount: int = Field(..., ge=10000, le=50000000,
                        description="Amount in VND")


class DepositResponse(BaseModel):
    client_secret: str
    payment_intent_id: str
    amount: int


class ConfirmDepositRequest(BaseModel):
    payment_intent_id: str


class ConfirmDepositResponse(BaseModel):
    payment_intent_id: str
    status: str
    message: str


class StripeConfigResponse(BaseModel):
    publishable_key: str


# ============================================================================
# Stripe Deposit (Topup)
# ============================================================================


@router.get("/config", response_model=StripeConfigResponse)
async def get_stripe_config():
    """Return Stripe publishable key to frontend dynamically."""
    from app.core.config import settings
    return StripeConfigResponse(publishable_key=settings.STRIPE_PUBLISHABLE_KEY)


@router.post("/create-deposit", response_model=DepositResponse)
async def create_deposit(
    current_user: CurrentUser,
    db: SessionDep,
    data: DepositRequest,
):
    """Create a Stripe PaymentIntent for wallet deposit.

    Returns client_secret for frontend to confirm with Stripe Elements.
    """
    wallet = await crud_wallet.get_or_create_wallet(db, current_user.id)
    amount_vnd = Decimal(str(data.amount))

    payment_data = await stripe_service.create_deposit_payment_intent(
        amount_vnd=amount_vnd,
        user_id=str(current_user.id),
        wallet_id=str(wallet.id),
    )

    tx = WalletTransaction(
        wallet_id=wallet.id,
        amount=amount_vnd,
        type=TransactionType.DEPOSIT_PENDING.value,
        description=f"Topup via Stripe: {amount_vnd:,.0f} VND",
        balance_before=wallet.balance,
        balance_after=wallet.balance,
        payment_gateway_ref=payment_data["payment_intent_id"],
        stripe_payment_intent_id=payment_data["payment_intent_id"],
        status="pending",
    )
    db.add(tx)
    await db.commit()

    return DepositResponse(
        client_secret=payment_data["client_secret"],
        payment_intent_id=payment_data["payment_intent_id"],
        amount=data.amount,
    )


@router.post("/confirm-deposit", response_model=ConfirmDepositResponse)
async def confirm_deposit(
    current_user: CurrentUser,
    db: SessionDep,
    data: ConfirmDepositRequest,
):
    """Finalize a deposit after Stripe confirms success.

    This is an idempotent fallback for cases where the webhook is delayed
    or not delivered yet. If the transaction is already completed, the
    handler exits without double-crediting the wallet.
    """
    payment_intent = await stripe_service.retrieve_payment_intent(data.payment_intent_id)
    metadata = payment_intent.metadata or {}
    metadata_user_id = None
    if isinstance(metadata, dict):
        metadata_user_id = metadata.get("user_id")
    elif hasattr(metadata, "to_dict"):
        metadata_user_id = metadata.to_dict().get("user_id")
    else:
        metadata_user_id = getattr(metadata, "user_id", None)

    if metadata_user_id and str(metadata_user_id) != str(current_user.id):
        raise HTTPException(
            status_code=403, detail="Không có quyền xác nhận giao dịch này")

    if payment_intent.status != "succeeded":
        return ConfirmDepositResponse(
            payment_intent_id=data.payment_intent_id,
            status=payment_intent.status,
            message="PaymentIntent chưa ở trạng thái succeeded",
        )

    await stripe_service._handle_payment_succeeded(payment_intent, db)

    return ConfirmDepositResponse(
        payment_intent_id=data.payment_intent_id,
        status="succeeded",
        message="Nạp tiền đã được đồng bộ vào ví",
    )


# ============================================================================
# Stripe Webhook
# ============================================================================


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
):
    """Receive Stripe webhook events (payment_intent, payout, etc.)."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(
            status_code=400, detail="Missing stripe-signature header")

    event = await stripe_service.verify_webhook_signature(
        payload=payload,
        sig_header=sig_header,
    )
    if event is None:
        raise HTTPException(
            status_code=400, detail="Invalid webhook signature")

    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        result = await stripe_service.handle_webhook_event(event, session)
        await session.commit()

    return {"status": result}
