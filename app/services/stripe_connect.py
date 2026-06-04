"""Stripe Connect service for marketplace seller onboarding and transfers.

Handles connected account creation, Stripe-hosted onboarding links,
and fund transfers to connected accounts.
"""
import logging
from decimal import Decimal

import stripe

from app.core.config import settings
from app.utils.currency import vnd_to_usd_cents

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY
STRIPE_CURRENCY = settings.STRIPE_CURRENCY


# ============================================================================
# Connected Account Management
# ============================================================================


async def create_connected_account(
    email: str,
    first_name: str,
    last_name: str,
    country: str = "US",
) -> dict:
    """Create a Stripe Connect Express account for a seller.

    Uses Express Dashboard to simplify KYC.
    In test mode, Stripe auto-verifies accounts — no real documents needed.

    Args:
        email: Seller's email
        first_name: Seller's first name
        last_name: Seller's last name
        country: ISO country code (default "US" for test mode)

    Returns:
        dict: { account_id, charges_enabled, payouts_enabled }

    Stripe docs:
    - https://docs.stripe.com/api/accounts/create
    - https://docs.stripe.com/connect/express-accounts
    """
    account = stripe.Account.create(
        type="express",
        country=country,
        email=email,
        capabilities={
            "card_payments": {"requested": True},
            "transfers": {"requested": True},
        },
        business_type="individual",
        metadata={
            "platform": "remarket",
        },
    )

    logger.info("Created connected account %s for %s", account.id, email)

    return {
        "account_id": account.id,
        "charges_enabled": account.charges_enabled,
        "payouts_enabled": account.payouts_enabled,
    }


async def create_account_onboarding_link(
    account_id: str,
    refresh_url: str,
    return_url: str,
) -> dict:
    """Create an Account Link for Stripe-hosted onboarding.

    Redirect the seller to the returned URL to complete KYC.
    In test mode, use test values:
        - DOB: 01/01/1901
        - SSN: 000-00-0000
        - Address: any valid US address

    Args:
        account_id: Stripe connected account ID (acct_xxx)
        refresh_url: URL to redirect if link expires
        return_url: URL to redirect after onboarding

    Returns:
        dict: { url }

    Stripe docs: https://docs.stripe.com/api/account_links/create
    """
    account_link = stripe.AccountLink.create(
        account=account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
        collection_options={
            "fields": "eventually_due",
        },
    )

    return {"url": account_link.url}


async def get_account_status(account_id: str) -> dict:
    """Check the status of a connected account.

    Returns:
        dict: { account_id, charges_enabled, payouts_enabled,
               requirements, onboarding_complete }
    """
    account = stripe.Account.retrieve(account_id)

    requirements = account.requirements.to_dict() if account.requirements else {}
    currently_due = requirements.get("currently_due", [])
    disabled_reason = requirements.get("disabled_reason")

    onboarding_complete = (
        account.charges_enabled
        and account.payouts_enabled
        and not currently_due
        and not disabled_reason
    )

    return {
        "account_id": account.id,
        "charges_enabled": account.charges_enabled,
        "payouts_enabled": account.payouts_enabled,
        "requirements": {
            "currently_due": currently_due,
            "eventually_due": requirements.get("eventually_due", []),
            "disabled_reason": disabled_reason,
        },
        "onboarding_complete": onboarding_complete,
    }


# ============================================================================
# Transfers (Escrow Release → Seller)
# ============================================================================


async def transfer_to_connected_account(
    amount_vnd: Decimal,
    destination_account_id: str,
    order_id: str,
    description: str = "",
) -> dict:
    """Transfer funds from platform to seller's connected account.

    Called when escrow is released — money moves from the platform's
    Stripe balance to the seller's Stripe balance.

    Args:
        amount_vnd: Amount in VND
        destination_account_id: Seller's Stripe account ID
        order_id: Order UUID for metadata
        description: Human-readable description

    Returns:
        dict: { transfer_id, status, amount }

    Stripe docs: https://docs.stripe.com/api/transfers/create
    """
    amount_cents = vnd_to_usd_cents(amount_vnd)

    transfer = stripe.Transfer.create(
        amount=amount_cents,
        currency=STRIPE_CURRENCY,
        destination=destination_account_id,
        description=description or f"Payment for order {order_id}",
        metadata={
            "order_id": order_id,
            "type": "escrow_release",
        },
    )

    logger.info(
        "Transfer %s: %s cents to account %s (order %s)",
        transfer.id, amount_cents, destination_account_id, order_id,
    )

    return {
        "transfer_id": transfer.id,
        "status": transfer.to_dict().get("status", "pending"),
        "amount": int(amount_vnd),
    }


async def reverse_transfer(
    transfer_id: str,
    amount_vnd: Decimal | None = None,
) -> dict:
    """Reverse a transfer (when dispute results in refund).

    Args:
        transfer_id: Stripe Transfer ID (tr_xxx)
        amount_vnd: Amount to reverse (None = full)

    Returns:
        dict: { reversal_id, status }

    Stripe docs: https://docs.stripe.com/api/transfer_reversals/create
    """
    reversal_params = {}
    if amount_vnd is not None:
        reversal_params["amount"] = vnd_to_usd_cents(amount_vnd)

    reversal = stripe.TransferReversal.create(
        transfer_id,
        **reversal_params,
    )

    return {
        "reversal_id": reversal.id,
        "status": reversal.to_dict().get("status", "pending"),
    }
