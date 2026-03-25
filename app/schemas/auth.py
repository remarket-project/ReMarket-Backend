from typing import Optional
from pydantic import BaseModel, EmailStr, Field

from app.models import UserPrivate


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # User ID
    exp: int  # Expiration time


class RegisterRequest(BaseModel):
    """Dữ liệu Frontend gửi lên khi Đăng ký"""
    email: EmailStr
    password: str = Field(
        min_length=8, description="Mật khẩu tối thiểu 8 ký tự")
    full_name: str = Field(min_length=2, max_length=255)
    phone: Optional[str] = None


class LoginRequest(BaseModel):
    """Dữ liệu Frontend gửi lên khi Đăng nhập"""
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """Dữ liệu gửi lên khi Access Token hết hạn"""
    refresh_token: str


class TokenResponse(BaseModel):
    """Dữ liệu Backend trả về khi Đăng nhập thành công"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPrivate


class MessageResponse(BaseModel):
    """Generic response message."""
    message: str
