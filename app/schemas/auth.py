import re

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models import UserPrivate


def validate_password_complexity(password: str) -> str:
    """
    Validate password complexity requirements:
    - At least 12 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    - At least 1 special character (!@#$%^&*)

    Args:
        password: Password to validate

    Returns:
        password: If valid

    Raises:
        ValueError: If password doesn't meet complexity requirements
    """
    if len(password) < 12:
        raise ValueError("Mật khẩu phải có ít nhất 12 ký tự")

    if not re.search(r'[A-Z]', password):
        raise ValueError("Mật khẩu phải chứa ít nhất một ký tự in hoa")

    if not re.search(r'[a-z]', password):
        raise ValueError("Mật khẩu phải chứa ít nhất một ký tự thường")

    if not re.search(r'\d', password):
        raise ValueError("Mật khẩu phải chứa ít nhất một chữ số")

    if not re.search(r'[!@#$%^&*]', password):
        raise ValueError(
            "Mật khẩu phải chứa ít nhất một ký tự đặc biệt (!@#$%^&*)")

    return password


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # User ID
    exp: int  # Expiration time


class RegisterRequest(BaseModel):
    """Dữ liệu Frontend gửi lên khi Đăng ký"""
    email: EmailStr
    password: str = Field(
        min_length=12, description="Mật khẩu: 12+ ký tự, 1 in hoa, 1 thường, 1 số, 1 ký tự đặc biệt")
    full_name: str = Field(min_length=2, max_length=255)
    phone: str | None = None

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_complexity(v)


class LoginRequest(BaseModel):
    """Dữ liệu Frontend gửi lên khi Đăng nhập"""
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """Dữ liệu gửi lên khi Access Token hết hạn"""
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    """Dữ liệu gửi lên khi xác minh email"""
    token: str


class ChangePasswordRequest(BaseModel):
    """Dữ liệu gửi lên khi đổi mật khẩu"""
    current_password: str = Field(..., description="Mật khẩu hiện tại")
    new_password: str = Field(
        min_length=12, description="Mật khẩu mới: 12+ ký tự, 1 in hoa, 1 thường, 1 số, 1 ký tự đặc biệt")
    confirm_password: str = Field(..., description="Xác nhận mật khẩu mới")

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_complexity(v)


class TokenResponse(BaseModel):
    """Dữ liệu Backend trả về khi Đăng nhập thành công"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPrivate


class ResendVerificationRequest(BaseModel):
    """Dữ liệu gửi lên khi gửi lại email xác minh"""
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    """Dữ liệu gửi lên khi quên mật khẩu"""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Dữ liệu gửi lên khi đặt lại mật khẩu"""
    token: str
    new_password: str = Field(
        min_length=12, description="Mật khẩu mới: 12+ ký tự, 1 in hoa, 1 thường, 1 số, 1 ký tự đặc biệt")

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_complexity(v)


class MessageResponse(BaseModel):
    """Generic response message."""
    message: str
