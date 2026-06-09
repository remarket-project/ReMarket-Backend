import secrets
import warnings
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    BeforeValidator,
    EmailStr,
    Field,
    HttpUrl,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


def parse_cors(v: Any) -> list[str]:
    if isinstance(v, str):
        if v.startswith("[") and v.endswith("]"):
            import json
            try:
                result = json.loads(v)
                if isinstance(result, list):
                    return [str(i).strip() for i in result]
            except json.JSONDecodeError:
                pass
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list):
        return [str(i).strip() for i in v]
    raise ValueError(v)


# Resolve .env path: project_root/.env
ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    # Project Info
    PROJECT_NAME: str = "ReMarket API"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Database
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    # Database pool settings
    DB_ECHO: bool = False  # Set True only for debugging
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800  # 30 minutes

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL(self) -> str:
        import urllib.parse
        encoded_password = urllib.parse.quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{encoded_password}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Synchronous database URL for Alembic migrations (using psycopg v3)."""
        import urllib.parse
        encoded_password = urllib.parse.quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql+psycopg://{self.POSTGRES_USER}:{encoded_password}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # CORS
    BACKEND_CORS_ORIGINS: Annotated[list[str], BeforeValidator(parse_cors)] = Field(
        default=[
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://10.0.0.69:5174",
        ],
        validate_default=True,
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        """Strip trailing slashes from CORS origins."""
        return [origin.rstrip("/") for origin in self.BACKEND_CORS_ORIGINS]

    # Redis (optional - for real-time multi-instance)
    REDIS_URL: str | None = None

    # Frontend / Backend URLs
    FRONTEND_HOST: str = "http://localhost:5173"
    BACKEND_HOST: str = "http://localhost:8000"

    # Shipping (GHN)
    SHIPPING_PROVIDER: str = "ghn"
    GHN_API_URL: str = "https://dev-online-gateway.ghn.vn/shiip/public-api"
    GHN_TOKEN: str = ""
    GHN_SHOP_ID: int = 0
    GHN_FROM_PROVINCE_ID: int = 200  # Mặc định Hồ Chí Minh (theo GHN)
    GHN_FROM_DISTRICT_ID: int = 1440  # Quận 1 (theo GHN district_id)
    GHN_FROM_WARD_CODE: str = ""

    # Payment (Stripe Test Mode)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_CURRENCY: str = "usd"
    VND_USD_EXCHANGE_RATE: int = 25000

    # Auto order completion
    ORDER_AUTO_COMPLETE_HOURS: int = 48
    ORDER_AUTO_CHECK_INTERVAL_SECONDS: int = 60

    # Withdraw limits
    WITHDRAW_MIN_AMOUNT: int = 50000
    WITHDRAW_MAX_AMOUNT: int = 50000000

    # Offers
    OFFER_EXPIRE_HOURS: int = 48
    OFFER_EXPIRY_JOB_INTERVAL_MINUTES: int = 5

    # Email / SMTP
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None
    REQUIRE_EMAIL_VERIFICATION: bool = False
    EMAIL_VERIFICATION_EXPIRE_HOURS: int = 24

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if self.EMAILS_FROM_NAME is None:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    # Sentry (error tracking)
    SENTRY_DSN: HttpUrl | None = None

    # Admin
    FIRST_SUPERUSER: EmailStr | None = None
    FIRST_SUPERUSER_PASSWORD: str | None = None
    EMAIL_TEST_USER: str = "test@remarket.vn"

    # File Upload
    UPLOAD_DIR: str = "uploads"

    # MinIO Configuration (optional)
    MINIO_ENDPOINT: str | None = None
    MINIO_ACCESS_KEY: str | None = None
    MINIO_SECRET_KEY: str | None = None
    MINIO_BUCKET_NAME: str = "listings"
    MINIO_USE_SSL: bool = False
    MINIO_PUBLIC_ENDPOINT: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def use_minio(self) -> bool:
        """Determine if MinIO should be used instead of local filesystem"""
        return bool(self.MINIO_ENDPOINT and self.MINIO_ACCESS_KEY and self.MINIO_SECRET_KEY)

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=2)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )
        return self


settings = Settings()  # type: ignore
