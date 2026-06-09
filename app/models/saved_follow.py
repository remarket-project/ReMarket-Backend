"""Saved listings and follow models."""
import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SavedListing(SQLModel, table=True):
    __tablename__ = "saved_listings" # type: ignore 

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    listing_id: uuid.UUID = Field(foreign_key="listings.id")
    saved_at: datetime = Field(default_factory=now)


class FollowSeller(SQLModel, table=True):
    __tablename__ = "follow_sellers" # type: ignore

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    follower_id: uuid.UUID = Field(foreign_key="users.id")
    followee_id: uuid.UUID = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=now)
