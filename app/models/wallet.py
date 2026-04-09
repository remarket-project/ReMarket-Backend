"""
Wallet and WalletTransaction models for ReMarket.

Handles user wallets, balances, and transaction history.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, String, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.order import Order


def get_datetime_utc() -> datetime:
    """Get current datetime in UTC."""
    return datetime.now(timezone.utc)


# ============================================================================
# Database Models
# ============================================================================

class Wallet(SQLModel, table=True):
    """User wallet model."""

    __tablename__ = "wallets"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="users.id",
        ondelete="CASCADE",
        unique=True,
        index=True
    )

    balance: Decimal = Field(
        default=Decimal("0.00"),
        max_digits=12,
        decimal_places=2,
        description="Available balance"
    )
    locked_balance: Decimal = Field(
        default=Decimal("0.00"),
        max_digits=12,
        decimal_places=2,
        description="Balance locked in escrow"
    )

    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    # Relationships
    user: "User" = Relationship(back_populates="wallet")
    transactions: list["WalletTransaction"] = Relationship(
        back_populates="wallet",
        cascade_delete=True
    )


class WalletTransaction(SQLModel, table=True):
    """Wallet transaction history model."""

    __tablename__ = "wallet_transactions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    wallet_id: uuid.UUID = Field(
        foreign_key="wallets.id",
        ondelete="CASCADE",
        index=True
    )

    amount: Decimal = Field(
        max_digits=12,
        decimal_places=2,
        description="Transaction amount (positive or negative)"
    )
    type: str = Field(
        sa_column=Column(String(50)),
        description="Transaction type"
    )
    description: Optional[str] = Field(default=None, max_length=500)

    # References to related entities
    order_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="orders.id",
        ondelete="SET NULL"
    )
    escrow_id: Optional[uuid.UUID] = Field(default=None)

    # Balance tracking
    balance_before: Decimal = Field(
        max_digits=12,
        decimal_places=2,
        description="Balance before this transaction"
    )
    balance_after: Decimal = Field(
        max_digits=12,
        decimal_places=2,
        description="Balance after this transaction"
    )

    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
        index=True
    )

    # Relationships
    wallet: Wallet = Relationship(back_populates="transactions")
