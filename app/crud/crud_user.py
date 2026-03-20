"""
CRUD operations for User model.

Pure database operations (no business logic).
"""
import uuid

from sqlmodel import Session, select

from app.models import User, UserCreate, UserRegister
from app.core.security import get_password_hash, hash_token


async def get_user_by_email(db: Session, email: str) -> User | None:
    """Get user by email. Returns None if not found."""
    statement = select(User).where(User.email == email)
    return db.exec(statement).first()


async def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    """Get user by ID. Returns None if not found."""
    return db.get(User, user_id)


async def create_user(db: Session, user_in: UserCreate | UserRegister) -> User:
    """
    Create a new user in database.

    Args:
        db: Database session
        user_in: User creation data

    Returns:
        Created User object
    """
    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        password_hash=get_password_hash(user_in.password),
        phone=getattr(user_in, 'phone', None)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


async def update_user(db: Session, user: User, user_in) -> User:
    """
    Update existing user.

    Args:
        db: Database session
        user: Existing User object
        user_in: Data to update

    Returns:
        Updated User object
    """
    from app.models import UserUpdate

    if isinstance(user_in, UserUpdate):
        update_data = user_in.model_dump(exclude_unset=True)
    else:
        update_data = user_in.model_dump(
            exclude_unset=True, exclude="password")
        if "password" in user_in and user_in.password:
            update_data["password_hash"] = get_password_hash(user_in.password)

    for field, value in update_data.items():
        if hasattr(user, field) and value is not None:
            setattr(user, field, value)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


async def update_user_refresh_token(
    db: Session, user_id: uuid.UUID, refresh_token: str | None
) -> None:
    """
    Update user's refresh token (hashed).

    Args:
        db: Database session
        user_id: User ID
        refresh_token: Refresh token (will be hashed). None = revoke token
    """
    user = await get_user_by_id(db, user_id)
    if user:
        if refresh_token:
            user.hashed_refresh_token = hash_token(refresh_token)
        else:
            user.hashed_refresh_token = None
        db.add(user)
        db.commit()


async def get_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    """Get list of users with pagination."""
    statement = select(User).offset(skip).limit(limit)
    return db.exec(statement).all()


async def get_users_count(db: Session) -> int:
    """Get total count of users."""
    statement = select(User)
    return len(db.exec(statement).all())
