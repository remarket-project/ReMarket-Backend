"""
CRUD operations for Wallet and WalletTransaction.

Handles wallet balance management and transaction history.
"""
import uuid
from decimal import Decimal
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc

from app.models.wallet import Wallet, WalletTransaction
from app.models.enums import TransactionType


async def get_wallet_by_user_id(
    db: AsyncSession,
    user_id: uuid.UUID
) -> Optional[Wallet]:
    """Get wallet by user ID."""
    result = await db.execute(
        select(Wallet).where(Wallet.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_or_create_wallet(
    db: AsyncSession,
    user_id: uuid.UUID
) -> Wallet:
    """
    Get wallet for user, create if doesn't exist.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        Wallet object
    """
    wallet = await get_wallet_by_user_id(db, user_id)

    if not wallet:
        wallet = Wallet(user_id=user_id)
        db.add(wallet)
        await db.commit()
        await db.refresh(wallet)

    return wallet


async def add_balance(
    db: AsyncSession,
    wallet_id: uuid.UUID,
    amount: Decimal,
    transaction_type: TransactionType,
    description: Optional[str] = None,
    order_id: Optional[uuid.UUID] = None,
    escrow_id: Optional[uuid.UUID] = None
) -> tuple[Wallet, WalletTransaction]:
    """
    Add to wallet balance and create transaction record.

    Args:
        db: Database session
        wallet_id: Wallet ID
        amount: Amount to add (positive value)
        transaction_type: Type of transaction
        description: Optional description
        order_id: Optional related order ID
        escrow_id: Optional related escrow ID

    Returns:
        Tuple of (updated Wallet, created Transaction)

    Raises:
        ValueError: If amount is negative
    """
    if amount < 0:
        raise ValueError("Amount must be positive")

    # Get wallet with row locking
    result = await db.execute(
        select(Wallet)
        .where(Wallet.id == wallet_id)
        .with_for_update(nowait=False)
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise ValueError("Wallet not found")

    # Record balance before transaction
    balance_before = wallet.balance

    # Update balance
    wallet.balance += amount
    wallet.updated_at = datetime.now(timezone.utc)

    # Create transaction record
    transaction = WalletTransaction(
        wallet_id=wallet_id,
        amount=amount,
        type=transaction_type.value,
        description=description,
        order_id=order_id,
        escrow_id=escrow_id,
        balance_before=balance_before,
        balance_after=wallet.balance
    )

    db.add(wallet)
    db.add(transaction)
    await db.commit()
    await db.refresh(wallet)
    await db.refresh(transaction)

    return wallet, transaction


async def lock_balance(
    db: AsyncSession,
    wallet_id: uuid.UUID,
    amount: Decimal,
    order_id: uuid.UUID,
    description: Optional[str] = None
) -> tuple[Wallet, WalletTransaction]:
    """
    Lock balance for escrow.

    Moves funds from available balance to locked_balance.

    Args:
        db: Database session
        wallet_id: Wallet ID
        amount: Amount to lock
        order_id: Related order ID
        description: Optional description

    Returns:
        Tuple of (updated Wallet, created Transaction)

    Raises:
        ValueError: If insufficient balance
    """
    if amount < 0:
        raise ValueError("Amount must be positive")

    # Get wallet with row locking
    result = await db.execute(
        select(Wallet)
        .where(Wallet.id == wallet_id)
        .with_for_update(nowait=False)
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise ValueError("Wallet not found")

    if wallet.balance < amount:
        raise ValueError(
            f"Insufficient balance. Available: {wallet.balance}, Required: {amount}")

    # Record balance before
    balance_before = wallet.balance

    # Lock balance
    wallet.balance -= amount
    wallet.locked_balance += amount
    wallet.updated_at = datetime.now(timezone.utc)

    # Create transaction record
    transaction = WalletTransaction(
        wallet_id=wallet_id,
        amount=-amount,  # Negative because it's deducted from available balance
        type=TransactionType.ESCROW_LOCK.value,
        description=description or f"Locked for order {order_id}",
        order_id=order_id,
        balance_before=balance_before,
        balance_after=wallet.balance
    )

    db.add(wallet)
    db.add(transaction)
    await db.commit()
    await db.refresh(wallet)
    await db.refresh(transaction)

    return wallet, transaction


async def unlock_balance(
    db: AsyncSession,
    wallet_id: uuid.UUID,
    amount: Decimal,
    order_id: uuid.UUID,
    description: Optional[str] = None
) -> tuple[Wallet, WalletTransaction]:
    """
    Unlock balance from escrow (refund to available balance).

    Args:
        db: Database session
        wallet_id: Wallet ID
        amount: Amount to unlock
        order_id: Related order ID
        description: Optional description

    Returns:
        Tuple of (updated Wallet, created Transaction)
    """
    if amount < 0:
        raise ValueError("Amount must be positive")

    # Get wallet with row locking
    result = await db.execute(
        select(Wallet)
        .where(Wallet.id == wallet_id)
        .with_for_update(nowait=False)
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise ValueError("Wallet not found")

    if wallet.locked_balance < amount:
        raise ValueError(
            f"Insufficient locked balance. Locked: {wallet.locked_balance}, Required: {amount}")

    # Record balance before
    balance_before = wallet.balance

    # Unlock balance
    wallet.locked_balance -= amount
    wallet.balance += amount
    wallet.updated_at = datetime.now(timezone.utc)

    # Create transaction record
    transaction = WalletTransaction(
        wallet_id=wallet_id,
        amount=amount,  # Positive because it's added back to available balance
        type=TransactionType.ESCROW_REFUND.value,
        description=description or f"Refund from order {order_id}",
        order_id=order_id,
        balance_before=balance_before,
        balance_after=wallet.balance
    )

    db.add(wallet)
    db.add(transaction)
    await db.commit()
    await db.refresh(wallet)
    await db.refresh(transaction)

    return wallet, transaction


async def transfer_locked_to_user(
    db: AsyncSession,
    from_wallet_id: uuid.UUID,
    to_wallet_id: uuid.UUID,
    amount: Decimal,
    order_id: uuid.UUID,
    description: Optional[str] = None
) -> tuple[Wallet, Wallet, WalletTransaction, WalletTransaction]:
    """
    Transfer locked funds from buyer to seller (escrow release).

    Args:
        db: Database session
        from_wallet_id: Buyer wallet ID (has locked balance)
        to_wallet_id: Seller wallet ID
        amount: Amount to transfer
        order_id: Related order ID
        description: Optional description

    Returns:
        Tuple of (buyer_wallet, seller_wallet, buyer_tx, seller_tx)
    """
    if amount < 0:
        raise ValueError("Amount must be positive")

    # Get both wallets with row locking (order by ID to prevent deadlock)
    result = await db.execute(
        select(Wallet)
        .where(Wallet.id.in_([from_wallet_id, to_wallet_id]))
        .order_by(Wallet.id)
        .with_for_update(nowait=False)
    )
    wallets = {w.id: w for w in result.scalars().all()}

    from_wallet = wallets.get(from_wallet_id)
    to_wallet = wallets.get(to_wallet_id)

    if not from_wallet or not to_wallet:
        raise ValueError("One or both wallets not found")

    if from_wallet.locked_balance < amount:
        raise ValueError(
            f"Insufficient locked balance. Locked: {from_wallet.locked_balance}, Required: {amount}")

    # Record balances before
    from_balance_before = from_wallet.balance
    to_balance_before = to_wallet.balance

    # Transfer: remove from locked, add to seller
    from_wallet.locked_balance -= amount
    to_wallet.balance += amount

    from_wallet.updated_at = datetime.now(timezone.utc)
    to_wallet.updated_at = datetime.now(timezone.utc)

    # Create transaction records
    from_tx = WalletTransaction(
        wallet_id=from_wallet_id,
        # Negative (locked balance decrease doesn't affect available)
        amount=-amount,
        type=TransactionType.ESCROW_RELEASE.value,
        description=description or f"Escrow released for order {order_id}",
        order_id=order_id,
        balance_before=from_balance_before,
        balance_after=from_wallet.balance
    )

    to_tx = WalletTransaction(
        wallet_id=to_wallet_id,
        amount=amount,  # Positive
        type=TransactionType.ESCROW_RELEASE.value,
        description=description or f"Payment received for order {order_id}",
        order_id=order_id,
        balance_before=to_balance_before,
        balance_after=to_wallet.balance
    )

    db.add(from_wallet)
    db.add(to_wallet)
    db.add(from_tx)
    db.add(to_tx)
    await db.commit()
    await db.refresh(from_wallet)
    await db.refresh(to_wallet)
    await db.refresh(from_tx)
    await db.refresh(to_tx)

    return from_wallet, to_wallet, from_tx, to_tx


async def get_wallet_transactions(
    db: AsyncSession,
    wallet_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20
) -> tuple[list[WalletTransaction], int]:
    """
    Get paginated wallet transaction history.

    Args:
        db: Database session
        wallet_id: Wallet ID
        skip: Number of records to skip
        limit: Maximum records to return

    Returns:
        Tuple of (transactions list, total count)
    """
    # Count total
    count_result = await db.execute(
        select(func.count())
        .select_from(WalletTransaction)
        .where(WalletTransaction.wallet_id == wallet_id)
    )
    total = count_result.scalar_one()

    # Get transactions
    result = await db.execute(
        select(WalletTransaction)
        .where(WalletTransaction.wallet_id == wallet_id)
        .order_by(desc(WalletTransaction.created_at))
        .offset(skip)
        .limit(limit)
    )
    transactions = list(result.scalars().all())

    return transactions, total
