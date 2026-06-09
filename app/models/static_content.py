"""Static content pages model for help/legal/contact."""
import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class StaticContent(SQLModel, table=True):
    __tablename__ = "static_contents" # type: ignore

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    key: str = Field(max_length=100, index=True)
    title: str = Field(max_length=255)
    body: str = Field(default="")
    locale: str = Field(default="vi")
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
