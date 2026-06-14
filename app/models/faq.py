import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class FaqChunk(SQLModel, table=True):
    __tablename__ = "faq_chunks"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    question: str = Field(max_length=500)
    answer: str = Field(sa_column=Column(Text, nullable=False))
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(Vector(384)),
    )
