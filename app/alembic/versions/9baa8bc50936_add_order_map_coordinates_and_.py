"""add_order_map_coordinates_and_simulation_timers

Revision ID: 9baa8bc50936
Revises: 8745f8284e98
Create Date: 2026-06-18 10:52:03.795173

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision = '9baa8bc50936'
down_revision = '8745f8284e98'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('orders', sa.Column('auto_ship_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('auto_deliver_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('seller_lat', sa.Float(), nullable=True))
    op.add_column('orders', sa.Column('seller_lng', sa.Float(), nullable=True))
    op.add_column('orders', sa.Column('shipping_lat', sa.Float(), nullable=True))
    op.add_column('orders', sa.Column('shipping_lng', sa.Float(), nullable=True))

    op.create_index('ix_orders_auto_ship_at', 'orders', ['auto_ship_at'], postgresql_using='btree')
    op.create_index('ix_orders_auto_deliver_at', 'orders', ['auto_deliver_at'], postgresql_using='btree')


def downgrade():
    op.drop_index('ix_orders_auto_deliver_at', table_name='orders')
    op.drop_index('ix_orders_auto_ship_at', table_name='orders')

    op.drop_column('orders', 'shipping_lng')
    op.drop_column('orders', 'shipping_lat')
    op.drop_column('orders', 'seller_lng')
    op.drop_column('orders', 'seller_lat')
    op.drop_column('orders', 'auto_deliver_at')
    op.drop_column('orders', 'auto_ship_at')
