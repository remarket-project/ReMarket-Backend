import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel
from app.models.enums import ConditionGrade, ListingStatus

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.category import Category
    from app.models.offer import Offer
    from app.models.order import Order


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


class ListingBase(SQLModel):
    title: str = Field(max_length=500)
    description: str | None = None
    price: Decimal = Field(max_digits=15, decimal_places=2)
    is_negotiable: bool = Field(default=True)
    condition_grade: ConditionGrade
    status: ListingStatus = Field(default=ListingStatus.PENDING)


class Listing(ListingBase, table=True):
    __tablename__ = "listings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    seller_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    category_id: uuid.UUID = Field(foreign_key="categories.id")

    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    seller: "User" = Relationship(back_populates="listings")
    category: "Category" = Relationship(back_populates="listings")
    images: list["ListingImage"] = Relationship(
        back_populates="listing", cascade_delete=True
    )
    offers: list["Offer"] = Relationship(
        back_populates="listing", cascade_delete=True
    )
    orders: list["Order"] = Relationship(
        back_populates="listing", cascade_delete=True
    )


class ListingImageBase(SQLModel):
    image_url: str
    is_primary: bool = Field(default=False)


class ListingImage(ListingImageBase, table=True):
    __tablename__ = "listing_images"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    listing_id: uuid.UUID = Field(
        foreign_key="listings.id", ondelete="CASCADE")
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    listing: Listing = Relationship(back_populates="images")
