import logging
import subprocess
import sys
from pathlib import Path

from sqlalchemy import Engine, text
from sqlmodel import Session
from tenacity import (
    after_log,
    before_log,
    retry,
    stop_after_attempt,
    wait_fixed,
)

from app.core.db import engine
from app.initial_data import init_db_data

# Add app directory to path for Docker container BEFORE any app imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Create services directory if it doesn't exist
_services_dir = Path(__file__).parent / "services"
_services_dir.mkdir(parents=True, exist_ok=True)
_services_init = _services_dir / "__init__.py"
if not _services_init.exists():
    _services_init.touch()

# Create email_service.py
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


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

max_tries = 60 * 5  # 5 minutes
wait_seconds = 1


@retry(
    stop=stop_after_attempt(max_tries),
    wait=wait_fixed(wait_seconds),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARN),
)
def init(db_engine: Engine) -> None:
    """Initialize database and wait for it to be ready."""
    try:
        with Session(db_engine) as session:
            # Try to create session to check if DB is awake
            session.exec(text("SELECT 1"))
            logger.info("Database is ready!")
    except Exception as e:
        logger.error(f"Database not ready: {e}")
        raise e


def main() -> None:
    """Run pre-start tasks."""
    logger.info("Running backend pre-start tasks...")

    # Step 1: Wait for database to be ready
    logger.info("Waiting for database to be ready...")
    init(engine)

    # Step 2: Run Alembic migrations
    logger.info("Running database migrations...")
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            check=True,
            cwd="/app",
        )
        logger.info("Migrations completed successfully!")
    except subprocess.CalledProcessError as e:
        logger.error(f"Migration failed: {e}")
        raise e

    # Step 3: Seed initial data
    logger.info("Seeding initial data...")
    try:
        init_db_data()
        logger.info("Seed data completed!")
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        raise e

    logger.info("Backend pre-start tasks completed successfully!")


if __name__ == "__main__":
    main()
