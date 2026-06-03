"""Stripe payment gateway integration (Test Mode).

Handles PaymentIntents, Payouts, Refunds, and Webhook verification.
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import stripe
from sqlalchemy import select

from app.core.config import settings
from app.models.enums import TransactionType
from app.models.wallet import Wallet, WalletTransaction
from app.utils.currency import usd_cents_to_vnd, vnd_to_usd_cents

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY
STRIPE_CURRENCY = settings.STRIPE_CURRENCY


# ============================================================================
# Payment Intents (Deposit)
# ============================================================================


async def create_deposit_payment_intent(
    amount_vnd: Decimal,
    user_id: str,
    wallet_id: str,
) -> dict:
    """Create a Stripe PaymentIntent for wallet deposit.

    The client_secret is returned to the frontend so the user can
    confirm payment with Stripe Elements.
    """
    amount_cents = vnd_to_usd_cents(amount_vnd)

    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=STRIPE_CURRENCY,
        metadata={
            "user_id": user_id,
            "wallet_id": wallet_id,
            "type": "deposit",
        },
        payment_method_types=["card"],
        automatic_payment_methods={"enabled": False},
        description=f"ReMarket wallet deposit - {amount_vnd:,.0f} VND",
    )

    logger.info(
        "Created PaymentIntent %s for user %s: %s cents",
        intent.id, user_id, amount_cents,
    )

    return {
        "client_secret": intent.client_secret,
        "payment_intent_id": intent.id,
        "amount": int(amount_vnd),
    }


async def retrieve_payment_intent(payment_intent_id: str) -> stripe.PaymentIntent:
    """Retrieve a PaymentIntent from Stripe by ID."""
    return stripe.PaymentIntent.retrieve(payment_intent_id)


# ============================================================================
# Payouts (Withdrawal)
# ============================================================================


async def create_payout(
    amount_vnd: Decimal,
    destination_bank: dict[str, str],
    metadata: dict[str, str] | None = None,
) -> dict:
    """Create a Stripe Payout to send funds to a user's bank account.

    In test mode, Stripe simulates payouts using test bank account numbers.
    No real money moves.
    """
    amount_cents = vnd_to_usd_cents(amount_vnd)

    payout = stripe.Payout.create(
        amount=amount_cents,
        currency=STRIPE_CURRENCY,
        metadata={
            "type": "withdrawal",
            **(metadata or {}),
        },
        statement_descriptor="REMARKET WITHDRAW",
    )

    logger.info(
        "Created Payout %s: %s cents (status=%s)",
        payout.id, amount_cents, payout.status,
    )

    return {
        "payout_id": payout.id,
        "status": payout.status,
        "amount": int(amount_vnd),
        "arrival_date": payout.arrival_date,
    }


async def retrieve_payout(payout_id: str) -> stripe.Payout:
    """Retrieve a Payout from Stripe by ID."""
    return stripe.Payout.retrieve(payout_id)


# ============================================================================
# Refunds
# ============================================================================


async def refund_payment_intent(
    payment_intent_id: str,
    amount_vnd: Decimal | None = None,
) -> dict:
    """Refund a PaymentIntent partially or fully.
    """
    refund_params: dict[str, Any] = {
        "payment_intent": payment_intent_id,
    }
    if amount_vnd is not None:
        refund_params["amount"] = vnd_to_usd_cents(amount_vnd)

    refund = stripe.Refund.create(**refund_params)

    return {
        "refund_id": refund.id,
        "status": refund.status,
        "amount": int(amount_vnd) if amount_vnd else None,
    }


# ============================================================================
# Webhook
# ============================================================================


async def verify_webhook_signature(
    payload: bytes,
    sig_header: str,
) -> stripe.Event | None:
    """Verify and construct a Stripe webhook event.
    """
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
        return event
    except ValueError as e:
        logger.warning("Invalid webhook payload: %s", e)
        return None
    except stripe.error.SignatureVerificationError as e:
        logger.warning("Invalid webhook signature: %s", e)
        return None


async def handle_webhook_event(
    event: stripe.Event,
    db: Any,
) -> str:
    """Route a Stripe webhook event to its handler.
    """
    event_type = event.type
    data = event.data.object

    handlers = {
        "payment_intent.succeeded": _handle_payment_succeeded,
        "payment_intent.payment_failed": _handle_payment_failed,
        "payout.paid": _handle_payout_paid,
        "payout.failed": _handle_payout_failed,
    }

    handler = handlers.get(event_type)
    if handler:
        await handler(data, db)
        logger.info("Webhook %s handled", event_type)
        return "handled"

    logger.debug("Webhook %s ignored", event_type)
    return "ignored"


# ---------------------------------------------------------------------------
# Webhook handlers
# ---------------------------------------------------------------------------


async def _handle_payment_succeeded(
    payment_intent: stripe.PaymentIntent,
    db: Any,
) -> None:
    """Handle payment_intent.succeeded — credit the wallet."""
    metadata = payment_intent.metadata or {}
    wallet_id = metadata.get("wallet_id")
    if not wallet_id:
        logger.error("No wallet_id in PaymentIntent %s metadata", payment_intent.id)
        return

    amount_vnd = usd_cents_to_vnd(payment_intent.amount)

    tx_result = await db.execute(
        select(WalletTransaction).where(
            WalletTransaction.payment_gateway_ref == payment_intent.id,
            WalletTransaction.status == "pending",
        )
    )
    tx = tx_result.scalar_one_or_none()
    if not tx:
        logger.warning("No pending tx for PI %s", payment_intent.id)
        return

    wallet_result = await db.execute(
        select(Wallet)
        .where(Wallet.id == wallet_id)
        .with_for_update()
    )
    wallet = wallet_result.scalar_one_or_none()
    if not wallet:
        logger.error("Wallet %s not found", wallet_id)
        return

    tx.balance_before = wallet.balance
    wallet.balance += amount_vnd
    wallet.updated_at = datetime.now(timezone.utc)
    tx.balance_after = wallet.balance
    tx.status = "completed"
    tx.type = TransactionType.DEPOSIT.value
    tx.stripe_payment_intent_id = payment_intent.id

    db.add(wallet)
    db.add(tx)
    await db.commit()

    logger.info(
        "Deposit completed: wallet %s +%s VND (PI: %s)",
        wallet_id, amount_vnd, payment_intent.id,
    )


async def _handle_payment_failed(
    payment_intent: stripe.PaymentIntent,
    db: Any,
) -> None:
    """Handle payment_intent.payment_failed — mark transaction failed."""
    tx_result = await db.execute(
        select(WalletTransaction).where(
            WalletTransaction.payment_gateway_ref == payment_intent.id,
        )
    )
    tx = tx_result.scalar_one_or_none()
    if tx:
        tx.status = "failed"
        db.add(tx)
        await db.commit()

    logger.warning("Payment failed: PI %s", payment_intent.id)


async def _handle_payout_paid(
    payout: stripe.Payout,
    db: Any,
) -> None:
    """Handle payout.paid — mark withdrawal as completed."""
    tx_result = await db.execute(
        select(WalletTransaction).where(
            WalletTransaction.stripe_payout_id == payout.id,
        )
    )
    tx = tx_result.scalar_one_or_none()
    if not tx:
        tx_result = await db.execute(
            select(WalletTransaction).where(
                WalletTransaction.payment_gateway_ref == payout.id,
            )
        )
        tx = tx_result.scalar_one_or_none()
    if tx and tx.status == "pending":
        tx.status = "completed"
        tx.type = TransactionType.WITHDRAW_COMPLETED.value
        db.add(tx)
        await db.commit()
        logger.info("Withdraw completed: tx %s (payout %s)", tx.id, payout.id)


async def _handle_payout_failed(
    payout: stripe.Payout,
    db: Any,
) -> None:
    """Handle payout.failed — refund the wallet."""
    tx_result = await db.execute(
        select(WalletTransaction).where(
            WalletTransaction.stripe_payout_id == payout.id,
        )
    )
    tx = tx_result.scalar_one_or_none()
    if not tx:
        tx_result = await db.execute(
            select(WalletTransaction).where(
                WalletTransaction.payment_gateway_ref == payout.id,
            )
        )
        tx = tx_result.scalar_one_or_none()
    if not tx or tx.status != "pending":
        return

    refund_amount = abs(tx.amount)

    wallet_result = await db.execute(
        select(Wallet)
        .where(Wallet.id == tx.wallet_id)
        .with_for_update()
    )
    wallet = wallet_result.scalar_one_or_none()
    if not wallet:
        return

    tx.status = "failed"
    tx.type = TransactionType.WITHDRAW_FAILED.value

    wallet.balance += refund_amount
    wallet.updated_at = datetime.now(timezone.utc)

    refund_tx = WalletTransaction(
        wallet_id=wallet.id,
        amount=refund_amount,
        type=TransactionType.WITHDRAW_FAILED.value,
        description=f"Hoàn tiền rút thất bại: {refund_amount:,.0f} VND",
        balance_before=wallet.balance - refund_amount,
        balance_after=wallet.balance,
        status="completed",
    )

    db.add(wallet)
    db.add(tx)
    db.add(refund_tx)
    await db.commit()

    logger.info("Payout failed, refunded: tx %s (payout %s)", tx.id, payout.id)
