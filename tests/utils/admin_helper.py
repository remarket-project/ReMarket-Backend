"""Test helpers for admin API endpoints."""
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.crud_listing import create_listing
from app.crud.crud_user import create_user
from app.models import Category, Escrow, Listing, Order, User, Wallet
from app.models.enums import (
    ConditionGrade,
    EscrowStatus,
    ListingStatus,
    OrderStatus,
    UserRole,
)
from app.models.user import UserCreate
from tests.utils.utils import random_email, random_lower_string


async def create_test_category(db: AsyncSession) -> Category:
    slug = f"test-cat-{uuid.uuid4().hex[:8]}"
    category = Category(name="Test Category", slug=slug)
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


async def create_test_user(
    db: AsyncSession, is_admin: bool = False
) -> User:
    email = random_email()
    password = random_lower_string()
    full_name = random_lower_string()

    user_in = UserCreate(
        email=email,
        password=password,
        full_name=full_name,
        is_email_verified=True,
        role=UserRole.ADMIN if is_admin else UserRole.USER,
    )
    user = await create_user(db, user_in)
    return user


async def create_test_listing(
    db: AsyncSession,
    seller_id: uuid.UUID,
    category_id: uuid.UUID,
    status: ListingStatus = ListingStatus.PENDING,
    price: Optional[Decimal] = None,
) -> Listing:
    title = f"Test Listing {uuid.uuid4().hex[:8]}"
    price_val = price or Decimal("100000.00")

    listing = await create_listing(
        db,
        title=title,
        description="Test description for admin test",
        price=price_val,
        is_negotiable=True,
        condition_grade=ConditionGrade.GOOD,
        seller_id=str(seller_id),
        category_id=str(category_id),
    )
    if status != ListingStatus.PENDING:
        listing.status = status
        db.add(listing)
        await db.commit()
        await db.refresh(listing)

    return listing


async def create_test_wallet(
    db: AsyncSession,
    user_id: uuid.UUID,
    balance: Decimal = Decimal("1000000.00"),
) -> Wallet:
    wallet = Wallet(
        user_id=user_id, balance=balance, locked_balance=Decimal("0.00")
    )
    db.add(wallet)
    await db.commit()
    await db.refresh(wallet)
    return wallet


async def _get_or_create_wallet(
    db: AsyncSession, user_id: uuid.UUID
) -> Wallet:
    result = await db.execute(
        select(Wallet).where(Wallet.user_id == user_id)
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        wallet = Wallet(
            user_id=user_id,
            balance=Decimal("0.00"),
            locked_balance=Decimal("0.00"),
        )
        db.add(wallet)
        await db.commit()
        await db.refresh(wallet)
    return wallet


async def create_test_order_and_escrow(
    db: AsyncSession,
    buyer: User,
    seller: User,
    listing: Listing,
    escrow_status: EscrowStatus = EscrowStatus.DISPUTED,
) -> tuple[Order, Escrow]:
    from datetime import datetime, timezone

    buyer_wallet = await _get_or_create_wallet(db, buyer.id)
    seller_wallet = await _get_or_create_wallet(db, seller.id)

    amount = listing.price
    if buyer_wallet.balance < amount:
        buyer_wallet.balance = amount + Decimal("100000.00")
    if escrow_status in (EscrowStatus.DISPUTED, EscrowStatus.FUNDED):
        buyer_wallet.locked_balance = amount
        buyer_wallet.balance -= amount

    db.add(buyer_wallet)
    db.add(seller_wallet)
    await db.commit()
    await db.refresh(buyer_wallet)
    await db.refresh(seller_wallet)

    order = Order(
        buyer_id=buyer.id,
        seller_id=seller.id,
        listing_id=listing.id,
        final_price=amount,
        status=OrderStatus.PENDING,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    escrow = Escrow(
        order_id=order.id,
        amount=amount,
        status=escrow_status.value,
        buyer_wallet_id=buyer_wallet.id,
        seller_wallet_id=seller_wallet.id,
    )
    db.add(escrow)
    await db.commit()
    await db.refresh(escrow)

    if escrow_status == EscrowStatus.DISPUTED:
        from app.models.dispute import Dispute
        dispute = Dispute(
            order_id=order.id,
            raised_by=buyer.id,
            reason="Test dispute reason",
            status="open",
        )
        db.add(dispute)
        await db.commit()

    return order, escrow
