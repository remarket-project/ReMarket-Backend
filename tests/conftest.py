from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.db import engine, init_db
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models import Item, Listing, User
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        init_db(session)
        from app.initial_data import init_db_data
        init_db_data()
        yield session
        statement = delete(Item)
        session.execute(statement)
        statement = delete(User)
        session.execute(statement)
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )


# ============================================================================
# Async fixtures for admin tests
# ============================================================================

@pytest.fixture(scope="module")
async def async_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture(scope="module")
async def admin_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
async def admin_user(async_db: AsyncSession) -> Any:
    from sqlalchemy import select

    from app.models import User

    result = await async_db.execute(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    )
    return result.scalar_one_or_none()


@pytest.fixture(scope="module")
async def normal_user(async_db: AsyncSession) -> Any:
    from sqlalchemy import select

    from app.models import User

    result = await async_db.execute(
        select(User).where(User.email == settings.EMAIL_TEST_USER)
    )
    return result.scalar_one_or_none()
