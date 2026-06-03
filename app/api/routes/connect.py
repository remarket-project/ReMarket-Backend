"""Stripe Connect API endpoints — seller onboarding and account management.

Handles creating connected accounts, generating onboarding links,
and checking account status.
"""
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.crud import crud_wallet
from app.models.enums import TransactionType
from app.models.wallet import WalletTransaction
from app.services import stripe_connect

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connect", tags=["Stripe Connect"])


# ============================================================================
# Schemas
# ============================================================================


class CreateAccountResponse(BaseModel):
    account_id: str
    onboarding_url: str


class OnboardingStatusResponse(BaseModel):
    account_id: str | None
    onboarding_complete: bool
    account_status: str | None
    charges_enabled: bool
    payouts_enabled: bool


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/onboarding", response_model=CreateAccountResponse)
async def start_onboarding(
    current_user: CurrentUser,
    db: SessionDep,
):
    """Create a Stripe Connect Express account and return onboarding link.

    Seller is redirected to Stripe-hosted onboarding to complete KYC.
    In test mode, use test values:
        - DOB: 01/01/1901
        - SSN: 000-00-0000
        - Address: any valid US address
    """
    if current_user.stripe_account_id:
        account_id = current_user.stripe_account_id
        logger.info("User %s already has account %s", current_user.id, account_id)
    else:
        result = await stripe_connect.create_connected_account(
            email=current_user.email,
            first_name=current_user.full_name.split(" ", 1)[0],
            last_name=current_user.full_name.split(" ", 1)[1] if " " in current_user.full_name else "",
        )
        account_id = result["account_id"]

        current_user.stripe_account_id = account_id
        current_user.stripe_account_status = "pending"
        db.add(current_user)
        await db.commit()

    refresh_url = f"{settings.FRONTEND_HOST}/settings?tab=payment"
    return_url = f"{settings.FRONTEND_HOST}/settings?tab=payment&onboarding=complete"

    link = await stripe_connect.create_account_onboarding_link(
        account_id=account_id,
        refresh_url=refresh_url,
        return_url=return_url,
    )

    return CreateAccountResponse(
        account_id=account_id,
        onboarding_url=link["url"],
    )


@router.get("/onboarding/status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    current_user: CurrentUser,
    db: SessionDep,
):
    """Check the Stripe onboarding status of the current user."""
    if not current_user.stripe_account_id:
        return OnboardingStatusResponse(
            account_id=None,
            onboarding_complete=False,
            account_status=None,
            charges_enabled=False,
            payouts_enabled=False,
        )

    status_data = await stripe_connect.get_account_status(
        current_user.stripe_account_id
    )

    if status_data["onboarding_complete"] and not current_user.stripe_onboarding_complete:
        current_user.stripe_onboarding_complete = True
        current_user.stripe_account_status = "active"
        db.add(current_user)
        await db.commit()

    return OnboardingStatusResponse(
        account_id=current_user.stripe_account_id,
        onboarding_complete=status_data["onboarding_complete"],
        account_status=current_user.stripe_account_status,
        charges_enabled=status_data["charges_enabled"],
        payouts_enabled=status_data["payouts_enabled"],
    )
