"""CRUD for chat models (basic)."""
import uuid
from typing import Optional
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatConversation, Message, ConversationParticipant


async def create_conversation(db: AsyncSession, listing_id: Optional[uuid.UUID] = None) -> ChatConversation:
    conv = ChatConversation(listing_id=listing_id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def add_participant(db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID) -> ConversationParticipant:
    p = ConversationParticipant(
        conversation_id=conversation_id, user_id=user_id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


async def post_message(db: AsyncSession, conversation_id: uuid.UUID, sender_id: uuid.UUID, content: str) -> Message:
    m = Message(conversation_id=conversation_id,
                sender_id=sender_id, content=content)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def get_conversation_messages(db: AsyncSession, conversation_id: uuid.UUID):
    result = await db.execute(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()))
    return list(result.scalars().all())
