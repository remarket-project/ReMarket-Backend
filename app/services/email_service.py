from pathlib import Path
from typing import Any

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


def _render(template_name: str, context: dict[str, Any]) -> str:
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


async def send_password_reset_email(to_email: str, full_name: str, reset_token: str) -> bool:
    """Gửi email đặt lại mật khẩu"""
    reset_url = f"{settings.FRONTEND_HOST}/reset-password?token={reset_token}"
    html = _render(
        "reset_password.html",
        {
            "full_name": full_name,
            "reset_url": reset_url,
            "project_name": settings.PROJECT_NAME,
            "valid_hours": 24,  # Password reset tokens valid for 24 hours
        },
    )
    return await send_email(
        to_email=to_email,
        subject="Đặt lại mật khẩu của bạn",
        html_content=html,
        plain_content=f"Xin chào {full_name}, vui lòng nhấn vào liên kết sau để đặt lại mật khẩu: {reset_url}",
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
