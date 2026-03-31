"""
API dependencies - shared dependencies for all routes.
"""
from collections.abc import AsyncGenerator
from typing import Annotated, TypeAlias
import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import settings
from app.crud import crud_user
from app.db.session import AsyncSessionLocal
from app.models import User
from app.models.enums import UserRole
from app.schemas.auth import TokenPayload

# HTTPBearer scheme - simple Bearer token authentication
http_bearer = HTTPBearer()


# ============================================================================
# Database Session
# ============================================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        yield session


async def get_token(credentials=Depends(http_bearer)) -> str:
    """Extract Bearer token from credentials."""
    return credentials.credentials


SessionDep: TypeAlias = Annotated[AsyncSession, Depends(get_db)]
TokenDep: TypeAlias = Annotated[str, Depends(get_token)]


# ============================================================================
# Current User
# ============================================================================

async def get_current_user(
    session: SessionDep,
    token: TokenDep
) -> User:
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
    user = await crud_user.get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser: TypeAlias = Annotated[User, Depends(get_current_user)]


# ============================================================================
# Admin User
# ============================================================================

async def get_current_admin(current_user: CurrentUser) -> User:
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
