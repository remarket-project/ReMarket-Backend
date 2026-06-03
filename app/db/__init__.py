"""
Database session configuration with async support and connection pooling.
"""
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Create services directory on module import
_services_dir = Path(__file__).parent.parent / "services"
_services_dir.mkdir(parents=True, exist_ok=True)
(_services_dir / "__init__.py").touch()

# Create email_service.py if it doesn't exist
_email_service_file = _services_dir / "email_service.py"
if not _email_service_file.exists():
    _email_service_file.write_text('''from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings
from app.core.email import send_email
from app.models.order import Order
from app.models.user import User

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _render(template_name: str, context: dict) -> str:
    template = _env.get_template(template_name)
    return template.render(**context)


async def send_verify_email(to_email: str, full_name: str, verification_token: str) -> bool:
    """Gửi email xác minh"""
    verification_url = f"{settings.FRONTEND_HOST}/verify-email?token={verification_token}"
    html = _render(
        "verify_email.html",
        {
            "full_name": full_name,
            "verification_url": verification_url,
            "project_name": settings.PROJECT_NAME,
            "expires_hours": settings.EMAIL_VERIFICATION_EXPIRE_HOURS,
        },
    )
    return await send_email(
        to_email=to_email,
        subject="Xác minh email của bạn",
        html_content=html,
        plain_content=f"Xin chào {full_name}, vui lòng xác minh email: {verification_url}",
    )


async def send_welcome_email(to_email: str, full_name: str) -> bool:
    """Gửi email chào mừng"""
    html = _render(
        "welcome.html",
        {
            "full_name": full_name,
        },
    )
    return await send_email(
        to_email=to_email,
        subject="Chào mừng đến ReMarket",
        html_content=html,
        plain_content=f"Xin chào {full_name}, email của bạn đã được xác minh. Chào mừng đến ReMarket!",
    )


async def send_order_created_email(buyer: User, seller: User, order: Order, listing_title: str) -> None:
    """Gửi email khi đơn hàng được tạo"""
    buyer_html = _render(
        "order_created.html",
        {
            "full_name": buyer.full_name,
            "order_id": str(order.id),
            "listing_title": listing_title,
            "final_price": str(order.final_price),
            "role": "buyer",
        },
    )
    seller_html = _render(
        "order_created.html",
        {
            "full_name": seller.full_name,
            "order_id": str(order.id),
            "listing_title": listing_title,
            "final_price": str(order.final_price),
            "role": "seller",
        },
    )

    await send_email(
        to_email=buyer.email,
        subject="Đơn hàng được tạo thành công",
        html_content=buyer_html,
    )
    await send_email(
        to_email=seller.email,
        subject="Bạn nhận được đơn hàng mới",
        html_content=seller_html,
    )


async def send_order_completed_email(buyer: User, seller: User, order: Order) -> None:
    """Gửi email khi đơn hàng hoàn thành"""
    buyer_html = _render(
        "order_completed.html",
        {
            "full_name": buyer.full_name,
            "order_id": str(order.id),
            "final_price": str(order.final_price),
        },
    )
    seller_html = _render(
        "order_completed.html",
        {
            "full_name": seller.full_name,
            "order_id": str(order.id),
            "final_price": str(order.final_price),
        },
    )

    await send_email(
        to_email=buyer.email,
        subject="Đơn hàng hoàn thành",
        html_content=buyer_html,
    )
    await send_email(
        to_email=seller.email,
        subject="Đơn hàng hoàn thành",
        html_content=seller_html,
    )
''')

# Production-ready engine configuration with connection pooling
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,  # Configurable, default False in prod
    future=True,
    pool_size=settings.DB_POOL_SIZE,  # Default: 20
    max_overflow=settings.DB_MAX_OVERFLOW,  # Default: 10
    pool_timeout=settings.DB_POOL_TIMEOUT,  # Default: 30 seconds
    pool_recycle=settings.DB_POOL_RECYCLE,  # Default: 1800 (30 min)
    pool_pre_ping=True,  # Verify connections before use
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
    autoflush=False,  # Better control over when to flush
)


async def get_db():
    """Get database session for dependency injection."""
    async with AsyncSessionLocal() as session:
        yield session
