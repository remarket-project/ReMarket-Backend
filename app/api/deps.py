from collections.abc import Generator
from typing import Annotated, TypeAlias
import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.models import TokenPayload, User, UserRole

# OAuth2 scheme - points to login endpoint
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)


# ============================================================================
# Database Session
# ============================================================================

def get_db() -> Generator[Session, None, None]:
    """Get database session."""
    with Session(engine) as session:
        yield session


SessionDep: TypeAlias = Annotated[Session, Depends(get_db)]
TokenDep: TypeAlias = Annotated[str, Depends(reusable_oauth2)]


# ============================================================================
# Current User
# ============================================================================

def get_current_user(session: SessionDep, token: TokenDep) -> User:
    """
    Get current authenticated user from JWT token.

    Raises:
        HTTPException: If token invalid or user not found/inactive
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    user_id = uuid.UUID(token_data.sub)
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser: TypeAlias = Annotated[User, Depends(get_current_user)]


# ============================================================================
# Admin User
# ============================================================================

def get_current_admin(current_user: CurrentUser) -> User:
    """
    Get current authenticated user, verify they are admin.

    Raises:
        HTTPException: If user is not admin
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user


CurrentAdmin: TypeAlias = Annotated[User, Depends(get_current_admin)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user
