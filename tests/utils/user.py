import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.crud import crud_user
from app.models import User, UserCreate
from tests.utils.utils import random_email, random_lower_string


def _run_async(coro):
    return asyncio.run(coro)


def user_authentication_headers(
    *, client: TestClient, email: str, password: str
) -> dict[str, str]:
    data = {"username": email, "password": password}
    r = client.post(f"{settings.API_V1_STR}/auth/login", data=data)
    response = r.json()
    auth_token = response["access_token"]
    headers = {"Authorization": f"Bearer {auth_token}"}
    return headers


def create_random_user(db: Session) -> User:
    email = random_email()
    password = random_lower_string()
    full_name = random_lower_string()
    user_in = UserCreate(
        email=email,
        password=password,
        full_name=full_name,
        is_email_verified=True,
    )
    user = _run_async(crud_user.create_user(db, user_in))
    return user


def authentication_token_from_email(
    *, client: TestClient, email: str, db: Session
) -> dict[str, str]:
    password = random_lower_string()
    user = _run_async(crud_user.get_user_by_email(db, email=email))
    if not user:
        full_name = random_lower_string()
        user_in_create = UserCreate(
            email=email,
            password=password,
            full_name=full_name,
            is_email_verified=True,
        )
        user = _run_async(crud_user.create_user(db, user_in_create))
    else:
        user.password_hash = get_password_hash(password)
        db.add(user)
        db.commit()

    return user_authentication_headers(client=client, email=email, password=password)


async def create_random_user_async(db: AsyncSession) -> User:
    email = random_email()
    password = random_lower_string()
    full_name = random_lower_string()
    user_in = UserCreate(
        email=email,
        password=password,
        full_name=full_name,
        is_email_verified=True,
    )
    user = await crud_user.create_user(db, user_in)
    return user


async def authentication_token_from_email_async(
    client: TestClient, email: str, db: AsyncSession
) -> dict[str, str]:
    password = random_lower_string()
    user = await crud_user.get_user_by_email(db, email=email)
    if not user:
        full_name = random_lower_string()
        user_in_create = UserCreate(
            email=email,
            password=password,
            full_name=full_name,
            is_email_verified=True,
        )
        user = await crud_user.create_user(db, user_in_create)
    else:
        user.password_hash = get_password_hash(password)
        db.add(user)
        await db.commit()

    return user_authentication_headers(client=client, email=email, password=password)
