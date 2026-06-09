from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pwdlib.hashers.bcrypt import BcryptHasher
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash, verify_and_update_password, create_password_reset_token
from app.crud.crud_user import create_user
from app.models import User, UserCreate
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string


def test_get_access_token(client: TestClient) -> None:
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.post(f"{settings.API_V1_STR}/auth/login", data=login_data)
    tokens = r.json()
    assert r.status_code == 200
    assert "access_token" in tokens
    assert tokens["access_token"]


def test_get_access_token_incorrect_password(client: TestClient) -> None:
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": "incorrect",
    }
    r = client.post(f"{settings.API_V1_STR}/auth/login", data=login_data)
    assert r.status_code == 401


def test_use_access_token(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/users/me",
        headers=superuser_token_headers,
    )
    result = r.json()
    assert r.status_code == 200
    assert "email" in result


def test_recovery_password(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    with (
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.SMTP_USER", "admin@example.com"),
        patch("app.services.email_service.send_password_reset_email", return_value=None),
    ):
        email = "test@example.com"
        r = client.post(
            f"{settings.API_V1_STR}/auth/forgot-password",
            json={"email": email},
        )
        assert r.status_code == 200
        assert r.json() == {
            "message": "If your email is registered, you will receive a password reset link"
        }


def test_recovery_password_user_not_exits(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    email = "jVgQr@example.com"
    r = client.post(
        f"{settings.API_V1_STR}/auth/forgot-password",
        json={"email": email},
    )
    assert r.status_code == 200
    assert r.json() == {
        "message": "If your email is registered, you will receive a password reset link"
    }


@pytest.mark.asyncio
async def test_reset_password(client: TestClient, async_db: AsyncSession) -> None:
    email = random_email()
    password = random_lower_string()
    new_password = "newpassword123"

    user_create = UserCreate(
        email=email,
        full_name="Test User",
        password=password,
        is_active=True,
    )
    user = await create_user(db=async_db, user_in=user_create)
    token = create_password_reset_token(email=email)
    data = {"new_password": new_password, "token": token}

    r = client.post(
        f"{settings.API_V1_STR}/auth/reset-password",
        json=data,
    )

    assert r.status_code == 200
    assert r.json() == {"message": "Password reset successfully. Please login with your new password."}

    await async_db.refresh(user)
    verified, _ = verify_and_update_password(new_password, user.password_hash)
    assert verified


def test_reset_password_invalid_token(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"new_password": "changethispassword", "token": "invalid"}
    r = client.post(
        f"{settings.API_V1_STR}/auth/reset-password",
        json=data,
    )
    response = r.json()

    assert "detail" in response
    assert r.status_code == 400
    assert response["detail"] == "Invalid or expired reset token"


@pytest.mark.asyncio
async def test_login_with_bcrypt_password_upgrades_to_argon2(
    client: TestClient, async_db: AsyncSession
) -> None:
    """Test that logging in with a bcrypt password hash upgrades it to argon2."""
    email = random_email()
    password = random_lower_string()

    # Create a bcrypt hash directly (simulating legacy password)
    bcrypt_hasher = BcryptHasher()
    bcrypt_hash = bcrypt_hasher.hash(password)
    assert bcrypt_hash.startswith("$2")

    user = User(email=email, password_hash=bcrypt_hash, full_name="Test User", is_active=True, is_email_verified=True)
    async_db.add(user)
    await async_db.commit()
    await async_db.refresh(user)

    assert user.password_hash.startswith("$2")

    login_data = {"username": email, "password": password}
    r = client.post(f"{settings.API_V1_STR}/auth/login", data=login_data)
    assert r.status_code == 200
    tokens = r.json()
    assert "access_token" in tokens

    await async_db.refresh(user)

    # Verify the hash was upgraded to argon2
    assert user.password_hash.startswith("$argon2")

    verified, updated_hash = verify_and_update_password(password, user.password_hash)
    assert verified
    # Should not need another update since it's already argon2
    assert updated_hash is None


@pytest.mark.asyncio
async def test_login_with_argon2_password_keeps_hash(
    client: TestClient, async_db: AsyncSession
) -> None:
    """Test that logging in with an argon2 password hash does not update it."""
    email = random_email()
    password = random_lower_string()

    # Create an argon2 hash (current default)
    argon2_hash = get_password_hash(password)
    assert argon2_hash.startswith("$argon2")

    # Create user with argon2 hash
    user = User(email=email, password_hash=argon2_hash, full_name="Test User", is_active=True, is_email_verified=True)
    async_db.add(user)
    await async_db.commit()
    await async_db.refresh(user)

    original_hash = user.password_hash

    login_data = {"username": email, "password": password}
    r = client.post(f"{settings.API_V1_STR}/auth/login", data=login_data)
    assert r.status_code == 200
    tokens = r.json()
    assert "access_token" in tokens

    await async_db.refresh(user)

    assert user.password_hash == original_hash
    assert user.password_hash.startswith("$argon2")
