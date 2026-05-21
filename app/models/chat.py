"""
Chat models: Conversation, Message, Participant
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, String
from sqlmodel import Field, Relationship, SQLModel


def now():
    return datetime.now(timezone.utc)


class ChatConversation(SQLModel, table=True):
    __tablename__ = "chat_conversations"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    listing_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="listings.id")
    created_at: datetime = Field(
        default_factory=now, sa_type=DateTime(timezone=True))


class ConversationParticipant(SQLModel, table=True):
    __tablename__ = "conversation_participants"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(foreign_key="chat_conversations.id")
    user_id: uuid.UUID = Field(foreign_key="users.id")
    joined_at: datetime = Field(
        default_factory=now, sa_type=DateTime(timezone=True))


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(
        foreign_key="chat_conversations.id", index=True)
    sender_id: uuid.UUID = Field(foreign_key="users.id")
    content: str = Field(sa_column=String(2000))
    created_at: datetime = Field(
        default_factory=now, sa_type=DateTime(timezone=True))
