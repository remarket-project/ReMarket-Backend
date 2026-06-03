"""
Generate synthetic marketplace data for local development.

This script creates many users and listings so FE/BE flows can be tested
without relying on production data or scraping third-party websites.
"""

from __future__ import annotations

import argparse
import logging
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlmodel import Session, select

from app.core.db import engine
from app.core.security import get_password_hash
from app.models import (
    Category,
    ConditionGrade,
    Listing,
    ListingImage,
    ListingStatus,
    User,
    UserRole,
    Wallet,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


FIRST_NAMES = [
    "An",
    "Binh",
    "Chi",
    "Duc",
    "Giang",
    "Hanh",
    "Khanh",
    "Linh",
    "Minh",
    "Nam",
    "Ngoc",
    "Phuong",
    "Quang",
    "Trang",
    "Vy",
]

LAST_NAMES = [
    "Nguyen",
    "Tran",
    "Le",
    "Pham",
    "Hoang",
    "Vu",
    "Dang",
    "Do",
    "Bui",
    "Dinh",
]

ADJECTIVES = [
    "Clean",
    "Premium",
    "Lightweight",
    "Vintage",
    "Reliable",
    "Compact",
    "Original",
    "Classic",
    "Modern",
    "Limited",
]

PRODUCTS = [
    "MacBook Air M1",
    "Office Chair",
    "Mirrorless Camera",
    "Mechanical Keyboard",
    "iPhone 13",
    "Monitor 27 inch",
    "Gaming Console",
    "Leather Backpack",
    "Wireless Headphones",
    "Study Desk",
    "Bookshelf",
    "Coffee Table",
    "Running Shoes",
    "Jacket",
    "Smartwatch",
]

DESCRIPTIONS = [
    "Used carefully, all major functions work well, minor cosmetic wear only.",
    "Seller provides transparent condition notes and real photos.",
    "Good for daily usage, stable performance, ready to use.",
    "Kept in a smoke-free home, cleaned before shipping.",
    "Comes with basic accessories and secure packaging.",
]


@dataclass
class SeedConfig:
    users: int
    min_listings: int
    max_listings: int
    email_domain: str
    password: str
    prefix: str
    active_only: bool


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def random_full_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def random_title(rng: random.Random) -> str:
    return f"{rng.choice(ADJECTIVES)} {rng.choice(PRODUCTS)}"


def random_price(rng: random.Random) -> Decimal:
    base = rng.randint(25, 2200)
    cents = rng.choice([0, 49, 99])
    return Decimal(f"{base}.{cents:02d}")


def random_condition(rng: random.Random) -> ConditionGrade:
    return rng.choice(
        [
            ConditionGrade.LIKE_NEW,
            ConditionGrade.GOOD,
            ConditionGrade.FAIR,
            ConditionGrade.BRAND_NEW,
        ]
    )


def random_status(rng: random.Random, active_only: bool) -> ListingStatus:
    if active_only:
        return ListingStatus.ACTIVE
    return rng.choices(
        population=[
            ListingStatus.ACTIVE,
            ListingStatus.SOLD,
            ListingStatus.PENDING,
            ListingStatus.HIDDEN,
        ],
        weights=[75, 10, 10, 5],
        k=1,
    )[0]


def ensure_categories(session: Session) -> list[Category]:
    categories = list(session.exec(select(Category)).all())
    if categories:
        return categories

    fallback = [
        Category(name="Electronics", slug="electronics",
                 icon_url="https://picsum.photos/64?cat=electronics"),
        Category(name="Fashion", slug="fashion",
                 icon_url="https://picsum.photos/64?cat=fashion"),
        Category(name="Home", slug="home",
                 icon_url="https://picsum.photos/64?cat=home"),
        Category(name="Sports", slug="sports",
                 icon_url="https://picsum.photos/64?cat=sports"),
        Category(name="Books", slug="books",
                 icon_url="https://picsum.photos/64?cat=books"),
    ]
    session.add_all(fallback)
    session.commit()
    for cat in fallback:
        session.refresh(cat)

    logger.info("Created %s fallback categories", len(fallback))
    return fallback


def create_user(
    session: Session,
    cfg: SeedConfig,
    idx: int,
    rng: random.Random,
) -> tuple[User, bool]:
    stamp = now_utc().strftime("%Y%m%d")
    email = f"{cfg.prefix}.{stamp}.{idx:04d}@{cfg.email_domain}".lower()

    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        return existing, False

    user = User(
        email=email,
        full_name=random_full_name(rng),
        password_hash=get_password_hash(cfg.password),
        role=UserRole.USER,
        is_active=True,
        is_email_verified=True,
        bio="Trusted second-hand marketplace member",
        province=rng.choice(
            ["Ho Chi Minh City", "Hanoi", "Da Nang", "Can Tho"]),
        district="District " + str(rng.randint(1, 12)),
        trust_score=Decimal(str(rng.uniform(75.0, 98.0))
                            ).quantize(Decimal("0.1")),
        rating_avg=Decimal(str(rng.uniform(4.2, 5.0))
                           ).quantize(Decimal("0.01")),
        rating_count=rng.randint(8, 180),
        completed_orders=rng.randint(3, 120),
    )
    session.add(user)
    session.flush()

    wallet = Wallet(
        user_id=user.id,
        balance=Decimal(str(rng.randint(100, 3000))).quantize(Decimal("0.01")),
        locked_balance=Decimal(str(rng.randint(0, 900))
                               ).quantize(Decimal("0.01")),
    )
    session.add(wallet)

    return user, True


def create_listings_for_user(
    session: Session,
    user: User,
    categories: list[Category],
    cfg: SeedConfig,
    rng: random.Random,
) -> int:
    count = rng.randint(cfg.min_listings, cfg.max_listings)
    created = 0

    for _ in range(count):
        listing = Listing(
            title=random_title(rng),
            description=rng.choice(DESCRIPTIONS),
            price=random_price(rng),
            is_negotiable=rng.choice([True, True, False]),
            condition_grade=random_condition(rng),
            status=random_status(rng, cfg.active_only),
            seller_id=user.id,
            category_id=rng.choice(categories).id,
        )
        session.add(listing)
        session.flush()

        image_count = rng.randint(1, 4)
        for i in range(image_count):
            image = ListingImage(
                listing_id=listing.id,
                image_url=f"https://picsum.photos/seed/{uuid.uuid4().hex[:10]}/1200/900",
                is_primary=i == 0,
            )
            session.add(image)

        created += 1

    return created


def seed_marketplace(cfg: SeedConfig) -> None:
    if cfg.min_listings <= 0 or cfg.max_listings < cfg.min_listings:
        raise ValueError(
            "Invalid listing range. Ensure: min >= 1 and max >= min")

    rng = random.Random()

    users_created = 0
    listings_created = 0

    with Session(engine) as session:
        categories = ensure_categories(session)

        for idx in range(1, cfg.users + 1):
            user, is_new_user = create_user(session, cfg, idx, rng)
            if is_new_user:
                users_created += 1
            listings_created += create_listings_for_user(
                session=session,
                user=user,
                categories=categories,
                cfg=cfg,
                rng=rng,
            )

        session.commit()

    logger.info("Seed complete")
    logger.info("Users requested: %s", cfg.users)
    logger.info("Users created/new today: %s", users_created)
    logger.info("Listings created: %s", listings_created)
    logger.info("Each user target listings: %s-%s",
                cfg.min_listings, cfg.max_listings)


def parse_args() -> SeedConfig:
    parser = argparse.ArgumentParser(
        description="Seed synthetic marketplace users and listings")
    parser.add_argument("--users", type=int, default=40,
                        help="Number of users to create")
    parser.add_argument("--min-listings", type=int,
                        default=10, help="Minimum listings per user")
    parser.add_argument("--max-listings", type=int,
                        default=20, help="Maximum listings per user")
    parser.add_argument("--email-domain", type=str,
                        default="seed.remarket.local")
    parser.add_argument("--password", type=str, default="SeedPass@123")
    parser.add_argument("--prefix", type=str, default="seeduser")
    parser.add_argument(
        "--active-only",
        action="store_true",
        help="Create listings with active status only",
    )

    ns = parser.parse_args()
    return SeedConfig(
        users=ns.users,
        min_listings=ns.min_listings,
        max_listings=ns.max_listings,
        email_domain=ns.email_domain,
        password=ns.password,
        prefix=ns.prefix,
        active_only=ns.active_only,
    )


def main() -> None:
    cfg = parse_args()
    seed_marketplace(cfg)


if __name__ == "__main__":
    main()
