"""Currency conversion utilities — VND ↔ USD for Stripe."""

from decimal import Decimal

from app.core.config import settings

EXCHANGE_RATE = Decimal(str(settings.VND_USD_EXCHANGE_RATE))  # 25000


def vnd_to_usd_cents(vnd_amount: Decimal) -> int:
    """Convert VND to USD cents for Stripe.

    Stripe uses USD cents (e.g., $10.00 = 1000 cents).
    1 USD = EXCHANGE_RATE VND.

    Args:
        vnd_amount: Amount in VND (e.g., Decimal('100000'))

    Returns:
        Amount in USD cents (e.g., 400 for 100,000 VND @ 25000)
    """
    usd = vnd_amount / EXCHANGE_RATE
    return int(usd * 100)


def usd_cents_to_vnd(usd_cents: int) -> Decimal:
    """Convert Stripe USD cents back to VND.

    Args:
        usd_cents: Amount in USD cents (e.g., 400)

    Returns:
        Amount in VND (e.g., Decimal('100000') for 400 cents @ 25000)
    """
    usd = Decimal(str(usd_cents)) / Decimal("100")
    return usd * EXCHANGE_RATE
