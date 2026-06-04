"""Tests for Stripe payment integration — service layer and API endpoints."""
import json
from decimal import Decimal

import pytest
import stripe
from fastapi.testclient import TestClient

from app.core.config import settings
from app.utils.currency import vnd_to_usd_cents, usd_cents_to_vnd


# ============================================================================
# Currency Conversion
# ============================================================================

class TestCurrencyConversion:
    def test_vnd_to_usd_cents_standard(self):
        """100000 VND @ 26000 = ~3.84 USD = 384 cents"""
        result = vnd_to_usd_cents(Decimal("100000"))
        assert result == 384

    def test_vnd_to_usd_cents_zero(self):
        assert vnd_to_usd_cents(Decimal("0")) == 0

    def test_vnd_to_usd_cents_large(self):
        """50000000 VND = 192307 cents"""
        result = vnd_to_usd_cents(Decimal("50000000"))
        assert result == 192307

    def test_usd_cents_to_vnd(self):
        result = usd_cents_to_vnd(384)
        assert result == Decimal("99840.00")

    def test_round_trip(self):
        """VND -> cents -> VND should be close"""
        original = Decimal("500000")
        cents = vnd_to_usd_cents(original)
        back = usd_cents_to_vnd(cents)
        diff = abs(original - back)
        assert diff < Decimal("100"), f"Loss too large: {diff}"


# ============================================================================
# Stripe Service — Direct API Tests
# ============================================================================

class TestStripeService:
    """Tests that call Stripe API directly (test mode)."""

    def setup_method(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY

    def test_create_payment_intent(self):
        """Create a valid PaymentIntent"""
        intent = stripe.PaymentIntent.create(
            amount=384,
            currency="usd",
            metadata={"user_id": "test-user", "wallet_id": "test-wallet", "type": "deposit"},
            payment_method_types=["card"],
            automatic_payment_methods={"enabled": False},
            description="Test deposit",
        )
        assert intent.client_secret
        assert intent.amount == 384
        assert intent.metadata.type == "deposit"
        assert intent.status == "requires_payment_method"
        return intent

    def test_retrieve_payment_intent(self):
        intent = self.test_create_payment_intent()
        retrieved = stripe.PaymentIntent.retrieve(intent.id)
        assert retrieved.id == intent.id
        assert retrieved.amount == 384

    def test_payment_intent_confirm_and_refund(self):
        """Confirm with test card then refund"""
        intent = self.test_create_payment_intent()
        confirmed = stripe.PaymentIntent.confirm(intent.id, payment_method="pm_card_visa")
        assert confirmed.status == "succeeded"

        refund = stripe.Refund.create(payment_intent=confirmed.id)
        assert refund.status == "succeeded"

    def test_payment_intent_min_amount(self):
        """Stripe minimum is $0.50 = 50 cents"""
        intent = stripe.PaymentIntent.create(
            amount=50,
            currency="usd",
            payment_method_types=["card"],
            automatic_payment_methods={"enabled": False},
        )
        assert intent.id

    def test_payment_intent_too_small_fails(self):
        """1 cent should fail"""
        with pytest.raises(stripe.error.InvalidRequestError):
            stripe.PaymentIntent.create(
                amount=1,
                currency="usd",
                payment_method_types=["card"],
            )


    def test_create_payout(self):
        """Create payout to connected bank account."""
        balance = stripe.Balance.retrieve()
        usd_available = [a for a in balance.available if a.currency == "usd"]
        usd_pending = [p for p in balance.pending if p.currency == "usd"]
        avail_amount = usd_available[0].amount if usd_available else 0
        pending_amount = usd_pending[0].amount if usd_pending else 0

        if avail_amount == 0 and pending_amount == 0:
            pytest.skip(
                "No balance at all. First create a charge:\n"
                "  https://dashboard.stripe.com/test/balance/overview\n"
                "  Or run: python -c \"import stripe; stripe.PaymentIntent.create(amount=10000, currency='usd', payment_method_types=['card'])\""
            )

        payout_amt = min(10000, avail_amount) if avail_amount > 0 else min(5000, pending_amount)
        payout = stripe.Payout.create(
            amount=payout_amt,
            currency="usd",
            description="Test payout to STRIPE TEST BANK",
        )
        assert payout.id.startswith("po_")
        assert payout.amount > 0
        assert payout.status in ("pending", "paid"), (
            f"Unexpected payout status: {payout.status}"
        )


# ============================================================================
# Stripe Webhook Tests
# ============================================================================

class TestWebhook:
    """Test webhook signature verification and event handling."""

    def test_verify_valid_signature(self):
        """Valid signature should return event"""
        import hmac, hashlib, time
        whsec = settings.STRIPE_WEBHOOK_SECRET
        payload = json.dumps({
            "id": "evt_test_1",
            "object": "event",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_test", "object": "payment_intent", "amount": 384}},
        }).encode()
        ts = int(time.time())
        signed = f"{ts}.{payload.decode()}".encode()
        sig = hmac.new(whsec.encode(), signed, hashlib.sha256).hexdigest()
        sig_header = f"t={ts},v1={sig}"

        event = stripe.Webhook.construct_event(payload, sig_header, whsec)
        assert event.type == "payment_intent.succeeded"

    def test_verify_invalid_signature(self):
        """Invalid signature should raise"""
        import time
        whsec = settings.STRIPE_WEBHOOK_SECRET
        payload = b"{}"
        sig_header = f"t={int(time.time())},v1=badsignature"

        with pytest.raises(stripe.error.SignatureVerificationError):
            stripe.Webhook.construct_event(payload, sig_header, whsec)

    def test_verify_tampered_payload(self):
        """Payload modified after signing should fail"""
        import hmac, hashlib, time
        whsec = settings.STRIPE_WEBHOOK_SECRET
        payload = json.dumps({"id": "evt_test", "type": "payment_intent.succeeded"}).encode()
        ts = int(time.time())
        signed = f"{ts}.{payload.decode()}".encode()
        sig = hmac.new(whsec.encode(), signed, hashlib.sha256).hexdigest()

        tampered = json.dumps({"id": "evt_test", "type": "payment_intent.payment_failed"}).encode()
        sig_header = f"t={ts},v1={sig}"

        with pytest.raises(stripe.error.SignatureVerificationError):
            stripe.Webhook.construct_event(tampered, sig_header, whsec)


# ============================================================================
# Stripe Connect Tests
# ============================================================================

class TestStripeConnect:
    """Test Stripe Connect Express account creation and management."""

    def setup_method(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY

    def test_create_connected_account(self):
        """Create Express account for seller"""
        account = stripe.Account.create(
            type="express",
            country="US",
            email="test-seller@remarket.vn",
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
            business_type="individual",
            metadata={"platform": "remarket"},
        )
        assert account.id.startswith("acct_")
        assert account.type == "express"

        # Cleanup
        stripe.Account.delete(account.id)

    def test_account_link_creation(self):
        """Create onboarding link for a connected account"""
        account = stripe.Account.create(
            type="express",
            country="US",
            email="test-link@remarket.vn",
            capabilities={"card_payments": {"requested": True}, "transfers": {"requested": True}},
            business_type="individual",
        )
        link = stripe.AccountLink.create(
            account=account.id,
            refresh_url="http://localhost:5173/settings?tab=payment",
            return_url="http://localhost:5173/settings?tab=payment&onboarding=complete",
            type="account_onboarding",
        )
        assert link.url.startswith("https://connect.stripe.com/")

        # Cleanup
        stripe.Account.delete(account.id)

    def test_get_account_status(self):
        """Retrieve account details"""
        account = stripe.Account.create(
            type="express",
            country="US",
            email="test-status@remarket.vn",
            capabilities={"card_payments": {"requested": True}, "transfers": {"requested": True}},
            business_type="individual",
        )
        retrieved = stripe.Account.retrieve(account.id)
        assert retrieved.id == account.id
        assert hasattr(retrieved, "charges_enabled")
        assert hasattr(retrieved, "payouts_enabled")

        stripe.Account.delete(account.id)


# ============================================================================
# API Endpoint Tests
# ============================================================================

class TestPaymentAPI:
    """Test /api/v1/payment/ endpoints via TestClient."""

    def test_create_deposit_no_auth(self, client: TestClient):
        """Missing auth → 401"""
        r = client.post(f"{settings.API_V1_STR}/payment/create-deposit", json={"amount": 100000})
        assert r.status_code == 401

    def test_create_deposit_invalid_amount(self, client: TestClient, normal_user_token_headers):
        """Amount too small → 422"""
        r = client.post(
            f"{settings.API_V1_STR}/payment/create-deposit",
            headers=normal_user_token_headers,
            json={"amount": 1000},
        )
        assert r.status_code == 422

    def test_webhook_no_signature(self, client: TestClient):
        """Missing stripe-signature header → 400"""
        r = client.post(
            f"{settings.API_V1_STR}/payment/webhook",
            content=b"{}",
        )
        assert r.status_code == 400

    def test_webhook_bad_signature(self, client: TestClient):
        """Invalid signature → 400"""
        r = client.post(
            f"{settings.API_V1_STR}/payment/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=123,v1=badsig"},
        )
        assert r.status_code == 400


class TestConnectAPI:
    """Test /api/v1/connect/ endpoints."""

    def test_onboarding_no_auth(self, client: TestClient):
        r = client.post(f"{settings.API_V1_STR}/connect/onboarding")
        assert r.status_code == 401

    def test_onboarding_status_no_auth(self, client: TestClient):
        r = client.get(f"{settings.API_V1_STR}/connect/onboarding/status")
        assert r.status_code == 401


class TestWalletAPI:
    """Test /api/v1/wallet/ endpoints (Stripe-related)."""

    def test_withdraw_no_auth(self, client: TestClient):
        r = client.post(f"{settings.API_V1_STR}/wallet/withdraw", json={"amount": 100000})
        assert r.status_code == 401

    def test_withdraw_no_stripe_connect(self, client: TestClient, normal_user_token_headers):
        """User without Stripe Connect → 400"""
        r = client.post(
            f"{settings.API_V1_STR}/wallet/withdraw",
            headers=normal_user_token_headers,
            json={"amount": 100000},
        )
        assert r.status_code == 400
        assert "Stripe Connect" in r.text or "onboarding" in r.text
