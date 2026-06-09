"""Admin audit log model."""
import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AdminAuditLog(SQLModel, table=True):
    __tablename__ = "admin_audit_logs" # type: ignore

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    admin_id: uuid.UUID = Field(foreign_key="users.id")
    action: str = Field(max_length=255)
    target_type: str | None = Field(default=None, max_length=100)
    target_id: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=2000)
    created_at: datetime = Field(default_factory=now)
