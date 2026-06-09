import pytest
from fastapi.encoders import jsonable_encoder
from pwdlib.hashers.bcrypt import BcryptHasher
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.crud import crud_user
from app.core.security import verify_password, get_password_hash
from app.models import User, UserCreate, UserUpdate
from tests.utils.utils import random_email, random_lower_string


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    user = await crud_user.get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


@pytest.mark.asyncio
async def test_create_user(async_db: AsyncSession) -> None:
    email = random_email()
    password = random_lower_string()
    full_name = "Test User"
    user_in = UserCreate(email=email, password=password, full_name=full_name)
    user = await crud_user.create_user(db=async_db, user_in=user_in)
    assert user.email == email
    assert hasattr(user, "password_hash")


@pytest.mark.asyncio
async def test_authenticate_user(async_db: AsyncSession) -> None:
    email = random_email()
    password = random_lower_string()
    full_name = "Test User"
    user_in = UserCreate(email=email, password=password, full_name=full_name)
    user = await crud_user.create_user(db=async_db, user_in=user_in)
    authenticated_user = await authenticate(db=async_db, email=email, password=password)
    assert authenticated_user
    assert user.email == authenticated_user.email


@pytest.mark.asyncio
async def test_not_authenticate_user(async_db: AsyncSession) -> None:
    email = random_email()
    password = random_lower_string()
    user = await authenticate(db=async_db, email=email, password=password)
    assert user is None


@pytest.mark.asyncio
async def test_check_if_user_is_active(async_db: AsyncSession) -> None:
    email = random_email()
    password = random_lower_string()
    full_name = "Test User"
    user_in = UserCreate(email=email, password=password, full_name=full_name)
    user = await crud_user.create_user(db=async_db, user_in=user_in)
    assert user.is_active is True


@pytest.mark.asyncio
async def test_check_if_user_is_active_inactive(async_db: AsyncSession) -> None:
    email = random_email()
    password = random_lower_string()
    full_name = "Test User"
    user_in = UserCreate(email=email, password=password, full_name=full_name, is_active=False)
    user = await crud_user.create_user(db=async_db, user_in=user_in)
    assert user.is_active is False


@pytest.mark.asyncio
async def test_check_if_user_role_admin(async_db: AsyncSession) -> None:
    from app.models.enums import UserRole
    email = random_email()
    password = random_lower_string()
    full_name = "Test User"
    user_in = UserCreate(email=email, password=password, full_name=full_name, role=UserRole.ADMIN)
    user = await crud_user.create_user(db=async_db, user_in=user_in)
    assert user.role == UserRole.ADMIN


@pytest.mark.asyncio
async def test_check_if_user_role_normal(async_db: AsyncSession) -> None:
    from app.models.enums import UserRole
    username = random_email()
    password = random_lower_string()
    full_name = "Test User"
    user_in = UserCreate(email=username, password=password, full_name=full_name)
    user = await crud_user.create_user(db=async_db, user_in=user_in)
    assert user.role == UserRole.USER


@pytest.mark.asyncio
async def test_get_user(async_db: AsyncSession) -> None:
    password = random_lower_string()
    username = random_email()
    full_name = "Test User"
    user_in = UserCreate(email=username, password=password, full_name=full_name)
    user = await crud_user.create_user(db=async_db, user_in=user_in)
    user_2 = await crud_user.get_user_by_id(async_db, user.id)
    assert user_2
    assert user.email == user_2.email
    assert jsonable_encoder(user) == jsonable_encoder(user_2)


@pytest.mark.asyncio
async def test_update_user(async_db: AsyncSession) -> None:
    password = random_lower_string()
    email = random_email()
    full_name = "Test User"
    user_in = UserCreate(email=email, password=password, full_name=full_name)
    user = await crud_user.create_user(db=async_db, user_in=user_in)
    new_password = random_lower_string()
    user_in_update = UserUpdate(password=new_password)
    if user.id is not None:
        await crud_user.update_user(db=async_db, user_id=user.id, user_in=user_in_update)
    user_2 = await crud_user.get_user_by_id(async_db, user.id)
    assert user_2
    assert user.email == user_2.email


@pytest.mark.asyncio
async def test_authenticate_user_with_bcrypt_upgrades_to_argon2(async_db: AsyncSession) -> None:
    """Test that a user with bcrypt password hash gets upgraded to argon2 on login."""
    email = random_email()
    password = random_lower_string()

    # Create a bcrypt hash directly (simulating legacy password)
    bcrypt_hasher = BcryptHasher()
    bcrypt_hash = bcrypt_hasher.hash(password)
    assert bcrypt_hash.startswith("$2")  # bcrypt hashes start with $2

    # Create user with bcrypt hash directly in the database
    user = User(email=email, password_hash=bcrypt_hash, full_name="Test User", is_active=True, is_email_verified=True)
    async_db.add(user)
    await async_db.commit()
    await async_db.refresh(user)

    # Verify the hash is bcrypt before authentication
    assert user.password_hash.startswith("$2")

    # Authenticate - this should upgrade the hash to argon2
    # In auth.py route login, we do get_user_by_email and verify_password
    # Let's perform that check and simulate the upgrade
    db_user = await crud_user.get_user_by_email(async_db, email)
    assert db_user
    verified, updated_hash = verify_password(password, db_user.password_hash)
    assert verified
    
    # Check that verify_password returned the updated hash (since it was bcrypt)
    assert updated_hash is not None
    assert updated_hash.startswith("$argon2")
    
    # Save the updated hash to db (as done in login flow)
    db_user.password_hash = updated_hash
    async_db.add(db_user)
    await async_db.commit()
    await async_db.refresh(db_user)

    # Verify the hash was upgraded to argon2
    assert db_user.password_hash.startswith("$argon2")
