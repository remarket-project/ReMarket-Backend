"""CRUD for chat models (basic)."""
import uuid

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatConversation, ConversationParticipant, Message


async def create_conversation(
    db: AsyncSession,
    listing_id: uuid.UUID | None = None,
) -> ChatConversation:
    conversation = ChatConversation(listing_id=listing_id)
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def get_conversation_by_id(
    db: AsyncSession,
    conversation_id: uuid.UUID,
) -> ChatConversation | None:
    result = await db.execute(
        select(ChatConversation).where(ChatConversation.id == conversation_id)  # type: ignore[arg-type]
    )
    return result.scalar_one_or_none()


async def get_conversation_by_listing_and_user(
    db: AsyncSession,
    listing_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ChatConversation | None:
    result = await db.execute(
        select(ChatConversation)
        .join(
            ConversationParticipant,
            ConversationParticipant.conversation_id == ChatConversation.id,  # type: ignore[arg-type]
        )
        .where(
            ChatConversation.listing_id == listing_id,  # type: ignore[arg-type]
            ConversationParticipant.user_id == user_id,  # type: ignore[arg-type]
        )
        .order_by(desc(ChatConversation.created_at))
    )
    return result.scalar_one_or_none()


async def get_user_conversations(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[ChatConversation], int]:
    total = (
        await db.execute(
            select(func.count())
            .select_from(ChatConversation)
            .join(
                ConversationParticipant,
                ConversationParticipant.conversation_id == ChatConversation.id,  # type: ignore[arg-type]
            )
            .where(ConversationParticipant.user_id == user_id)  # type: ignore[arg-type]
        )
    ).scalar_one()

    result = await db.execute(
        select(ChatConversation)
        .join(
            ConversationParticipant,
            ConversationParticipant.conversation_id == ChatConversation.id,  # type: ignore[arg-type]
        )
        .where(ConversationParticipant.user_id == user_id)  # type: ignore[arg-type]
        .order_by(desc(ChatConversation.created_at))
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().unique().all()), int(total)


async def get_conversation_participants(
    db: AsyncSession,
    conversation_id: uuid.UUID,
) -> list[ConversationParticipant]:
    result = await db.execute(
        select(ConversationParticipant)
        .where(ConversationParticipant.conversation_id == conversation_id)  # type: ignore[arg-type]
        .order_by(asc(ConversationParticipant.joined_at))
    )
    return list(result.scalars().all())


async def add_participant(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ConversationParticipant:
    result = await db.execute(
        select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == conversation_id,  # type: ignore[arg-type]
            ConversationParticipant.user_id == user_id,  # type: ignore[arg-type]
        )
    )
    participant = result.scalar_one_or_none()
    if participant:
        return participant

    participant = ConversationParticipant(
        conversation_id=conversation_id,
        user_id=user_id,
    )
    db.add(participant)
    await db.commit()
    await db.refresh(participant)
    return participant


async def is_participant(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    result = await db.execute(
        select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == conversation_id,  # type: ignore[arg-type]
            ConversationParticipant.user_id == user_id,  # type: ignore[arg-type]
        )
    )
    return result.scalar_one_or_none() is not None


async def post_message(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    sender_id: uuid.UUID,
    content: str,
) -> Message:
    message = Message(
        conversation_id=conversation_id,
        sender_id=sender_id,
        content=content,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def get_conversation_messages(
    db: AsyncSession,
    conversation_id: uuid.UUID,
) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)  # type: ignore[arg-type]
        .order_by(asc(Message.created_at))
    )
    return list(result.scalars().all())
