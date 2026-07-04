"""add chat and saved tables

Revision ID: e34c9d8134bb
Revises: 9fe672333c5b
Create Date: 2026-07-04 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision = 'e34c9d8134bb'
down_revision = '9fe672333c5b'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Chat conversations
    op.create_table(
        'chat_conversations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('listing_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['listing_id'], ['listings.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # 2. Conversation participants
    op.create_table(
        'conversation_participants',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('conversation_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['chat_conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. Messages
    op.create_table(
        'messages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('conversation_id', sa.Uuid(), nullable=False),
        sa.Column('sender_id', sa.Uuid(), nullable=False),
        sa.Column('content', sa.String(length=2000), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['chat_conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 4. Saved listings
    op.create_table(
        'saved_listings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('listing_id', sa.Uuid(), nullable=False),
        sa.Column('saved_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['listing_id'], ['listings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 5. Follow sellers
    op.create_table(
        'follow_sellers',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('follower_id', sa.Uuid(), nullable=False),
        sa.Column('followee_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['followee_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['follower_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('follow_sellers')
    op.drop_table('saved_listings')
    op.drop_table('messages')
    op.drop_table('conversation_participants')
    op.drop_table('chat_conversations')
