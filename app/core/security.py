import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings

password_hash = PasswordHash(
    (
        Argon2Hasher(),
        BcryptHasher(),
    )
)


ALGORITHM = "HS256"


# ============================================================================
# Password Hashing
# ============================================================================

def get_password_hash(password: str) -> str:
    """Hash a password using Argon2 or Bcrypt."""
    return password_hash.hash(password)


def verify_password(
    plain_password: str, hashed_password: str
) -> tuple[bool, str | None]:
    """
    Verify password against hash.

    Returns:
        (is_valid, updated_hash_if_needed)
    """
    return password_hash.verify_and_update(plain_password, hashed_password)


# ============================================================================
# JWT Token
# ============================================================================

def create_access_token(subject: str | Any, expires_delta: timedelta) -> str:
    """Create JWT access token."""
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token() -> str:
    """
    Create a refresh token (random 32 bytes in hex format).

    This is NOT hashed yet - will be hashed before storage.
    """
    return secrets.token_hex(32)


# ============================================================================
# Token Hashing (for Refresh Token Storage)
# ============================================================================

def hash_token(token: str) -> str:
    """Hash token using SHA-256 for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token_hash(plain_token: str, hashed_token: str) -> bool:
    """Verify token against its hash."""
    return hash_token(plain_token) == hashed_token
