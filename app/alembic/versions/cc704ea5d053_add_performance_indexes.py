"""add_performance_indexes

Revision ID: cc704ea5d053
Revises: 9fe672333c5b
Create Date: 2026-06-12 14:01:37.251236

"""
from alembic import op
import sqlalchemy as sa


revision = 'cc704ea5d053'
down_revision = '9fe672333c5b'
branch_labels = None
depends_on = None


def upgrade():
    # Listing indexes
    op.create_index(op.f('ix_listings_status'), 'listings', ['status'], unique=False)
    op.create_index(op.f('ix_listings_seller_id'), 'listings', ['seller_id'], unique=False)
    op.create_index(op.f('ix_listings_category_id'), 'listings', ['category_id'], unique=False)
    op.create_index(op.f('ix_listings_created_at'), 'listings', ['created_at'], unique=False)

    # Order indexes
    op.create_index(op.f('ix_orders_listing_id'), 'orders', ['listing_id'], unique=False)

    # Offer indexes
    op.create_index(op.f('ix_offers_listing_id'), 'offers', ['listing_id'], unique=False)
    op.create_index(op.f('ix_offers_buyer_id'), 'offers', ['buyer_id'], unique=False)
    op.create_index(op.f('ix_offers_status'), 'offers', ['status'], unique=False)

    # Chat indexes
    op.create_index(op.f('ix_chat_conversations_listing_id'), 'chat_conversations', ['listing_id'], unique=False)
    op.create_index(op.f('ix_conversation_participants_conversation_id'), 'conversation_participants', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_conversation_participants_user_id'), 'conversation_participants', ['user_id'], unique=False)
    op.create_index(op.f('ix_messages_sender_id'), 'messages', ['sender_id'], unique=False)

    # Notification indexes
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_index(op.f('ix_notifications_is_read'), 'notifications', ['is_read'], unique=False)

    # Saved / Follow indexes
    op.create_index(op.f('ix_saved_listings_listing_id'), 'saved_listings', ['listing_id'], unique=False)
    op.create_index(op.f('ix_follow_sellers_followee_id'), 'follow_sellers', ['followee_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_listings_status'), table_name='listings')
    op.drop_index(op.f('ix_listings_seller_id'), table_name='listings')
    op.drop_index(op.f('ix_listings_category_id'), table_name='listings')
    op.drop_index(op.f('ix_listings_created_at'), table_name='listings')
    op.drop_index(op.f('ix_orders_listing_id'), table_name='orders')
    op.drop_index(op.f('ix_offers_listing_id'), table_name='offers')
    op.drop_index(op.f('ix_offers_buyer_id'), table_name='offers')
    op.drop_index(op.f('ix_offers_status'), table_name='offers')
    op.drop_index(op.f('ix_chat_conversations_listing_id'), table_name='chat_conversations')
    op.drop_index(op.f('ix_conversation_participants_conversation_id'), table_name='conversation_participants')
    op.drop_index(op.f('ix_conversation_participants_user_id'), table_name='conversation_participants')
    op.drop_index(op.f('ix_messages_sender_id'), table_name='messages')
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_is_read'), table_name='notifications')
    op.drop_index(op.f('ix_saved_listings_listing_id'), table_name='saved_listings')
    op.drop_index(op.f('ix_follow_sellers_followee_id'), table_name='follow_sellers')
