"""
Database initialization module.

Creates all tables on startup and migrates existing tables.
"""
from sqlmodel import SQLModel, text

import app.models.admin_audit  # noqa: F401

# Ensure model metadata is registered before create_all runs
import app.models.category  # noqa: F401
import app.models.chat  # noqa: F401
import app.models.listing  # noqa: F401
import app.models.notification  # noqa: F401
import app.models.offer  # noqa: F401
import app.models.order  # noqa: F401
import app.models.order_event  # noqa: F401
import app.models.review  # noqa: F401
import app.models.saved_follow  # noqa: F401
import app.models.static_content  # noqa: F401
import app.models.user  # noqa: F401
from app.db.session import engine

_MIGRATIONS: list[str] = [
    # ---- orders table ----
    """ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_method VARCHAR(20) NOT NULL DEFAULT 'wallet'""",
    """ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_provider VARCHAR(50)""",
    """ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_service_type INTEGER""",
    """ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_fee NUMERIC(12,2)""",
    """ALTER TABLE orders ADD COLUMN IF NOT EXISTS tracking_number VARCHAR(50)""",
    """CREATE INDEX IF NOT EXISTS ix_orders_tracking_number ON orders(tracking_number)""",
    """ALTER TABLE orders ADD COLUMN IF NOT EXISTS expected_delivery_at TIMESTAMP""",
    """ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP""",
    """ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_name VARCHAR(255)""",
    """ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_phone VARCHAR(20)""",
    """ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_province VARCHAR(100)""",
    """ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_district VARCHAR(100)""",
    """ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_ward VARCHAR(100)""",
    """ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_address_detail VARCHAR(255)""",
    """ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_note VARCHAR(500)""",
    """ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_province_id INTEGER""",
    """ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_district_id INTEGER""",
    """ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_ward_code VARCHAR(20)""",
    # ---- escrows table ----
    """ALTER TABLE escrows ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ""",
    """ALTER TABLE escrows ADD COLUMN IF NOT EXISTS auto_release_at TIMESTAMPTZ""",
    """ALTER TABLE escrows ADD COLUMN IF NOT EXISTS release_trigger VARCHAR(20)""",
    # ---- wallet_transactions table ----
    """ALTER TABLE wallet_transactions ADD COLUMN IF NOT EXISTS payment_gateway_ref VARCHAR(255)""",
    """ALTER TABLE wallet_transactions ADD COLUMN IF NOT EXISTS bank_code VARCHAR(50)""",
    """ALTER TABLE wallet_transactions ADD COLUMN IF NOT EXISTS bank_account VARCHAR(50)""",
    """ALTER TABLE wallet_transactions ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'completed'""",
]


async def init_db() -> None:
    """Initialize database tables and run migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        for stmt in _MIGRATIONS:
            await conn.execute(text(stmt))
