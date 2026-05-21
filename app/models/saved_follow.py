"""Saved listings and follow models."""
import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def now():
    return datetime.now(timezone.utc)


class SavedListing(SQLModel, table=True):
    __tablename__ = "saved_listings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    listing_id: uuid.UUID = Field(foreign_key="listings.id")
    saved_at: datetime = Field(default_factory=now)


class FollowSeller(SQLModel, table=True):
    __tablename__ = "follow_sellers"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    follower_id: uuid.UUID = Field(foreign_key="users.id")
    followee_id: uuid.UUID = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=now)
