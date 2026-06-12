"""
Chat models: Conversation, Message, Participant
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(timezone.utc)


class ChatConversation(SQLModel, table=True):
    __tablename__: str = "chat_conversations"  # type: ignore

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    listing_id: uuid.UUID | None = Field(
        default=None, foreign_key="listings.id", index=True)
    created_at: datetime = Field(
        default_factory=now, sa_column=Column(DateTime(timezone=True))
    )


class ConversationParticipant(SQLModel, table=True):
    __tablename__: str = "conversation_participants"  # type: ignore

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(foreign_key="chat_conversations.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    joined_at: datetime = Field(
        default_factory=now, sa_column=Column(DateTime(timezone=True))
    )


class Message(SQLModel, table=True):
    __tablename__: str = "messages"  # type: ignore

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(
        foreign_key="chat_conversations.id", index=True)
    sender_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    content: str = Field(max_length=2000)
    created_at: datetime = Field(
        default_factory=now, sa_column=Column(DateTime(timezone=True))
    )
