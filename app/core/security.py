import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings

pwd_context = PasswordHash(
    hashers=[
        Argon2Hasher(),
        BcryptHasher(),
    ]
)

ALGORITHM = "HS256"


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """Create JWT Access Token (short-lived, typically 7 days)."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(subject: str | Any) -> str:
    """Create JWT Refresh Token (long-lived, e.g., 30 days)."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh"  # Mark as refresh token
    }
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=ALGORITHM
    )
    return encoded_jwt


def hash_token(token: str) -> str:
    """Hash Refresh Token using SHA-256 for secure storage in database."""
    return hashlib.sha256(token.encode()).hexdigest()


def verify_and_update_password(plain_password: str, hashed_password: str) -> tuple[bool, str | None]:
    """Verify password and return whether it is valid, and optionally a new hash to upgrade to."""
    try:
        return pwd_context.verify_and_update(plain_password, hashed_password)
    except Exception:
        return False, None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify that input password matches stored hash."""
    return verify_and_update_password(plain_password, hashed_password)[0]


def get_password_hash(password: str) -> str:
    """Hash password before storing in database."""
    password = password
    # bcrypt/argon2 supports max 72 bytes; avoid runtime failure by truncating
    raw_bytes = password.encode("utf-8")
    if len(raw_bytes) > 72:
        password = raw_bytes[:72].decode("utf-8", errors="ignore")
    return pwd_context.hash(password)


def verify_token_hash(token: str, hashed_token: str) -> bool:
    """Verify that provided token matches stored hash."""
    return hash_token(token) == hashed_token


def create_email_verification_token(email: str) -> str:
    """Create email verification token."""
    expire = datetime.now(timezone.utc) + timedelta(
        hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS
    )
    to_encode = {
        "exp": expire,
        "sub": email,
        "type": "email_verification",
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_email_verification_token(token: str) -> str | None:
    """Decode and verify email verification token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[ALGORITHM])
        if payload.get("type") != "email_verification":
            return None
        email = payload.get("sub")
        if not isinstance(email, str):
            return None
        return email
    except Exception:
        return None


def create_password_reset_token(email: str) -> str:
    """Create password reset token."""
    expire = datetime.now(timezone.utc) + timedelta(hours=24)  # 24 hours
    to_encode = {
        "exp": expire,
        "sub": email,
        "type": "password_reset",
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_password_reset_token(token: str) -> str | None:
    """Decode and verify password reset token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[ALGORITHM])
        if payload.get("type") != "password_reset":
            return None
        email = payload.get("sub")
        if not isinstance(email, str):
            return None
        return email
    except Exception:
        return None


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode access token and return payload."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return {"error": "Token has expired"}
    except jwt.InvalidTokenError:
        return {"error": "Invalid token"}
    except Exception as e:
        return {"error": str(e)}
