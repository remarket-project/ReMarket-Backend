import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def _is_email_enabled() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


def _send_email_sync(to_email: str, subject: str, html_content: str, plain_content: str | None = None) -> bool:
    if not _is_email_enabled():
        logger.warning(
            "Email sending bị bỏ qua: SMTP không được cấu hình đầy đủ")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
    message["To"] = to_email
    message.set_content(
        plain_content or "Vui lòng xem tin nhắn này trong ứng dụng email hỗ trợ HTML.")
    message.add_alternative(html_content, subtype="html")

    host: str = settings.SMTP_HOST  # type: ignore[assignment]
    user: str = settings.SMTP_USER  # type: ignore[assignment]
    password: str = settings.SMTP_PASSWORD  # type: ignore[assignment]

    if settings.SMTP_SSL:
        with smtplib.SMTP_SSL(host, settings.SMTP_PORT) as server:
            server.login(user, password)
            server.send_message(message)
        return True

    with smtplib.SMTP(host, settings.SMTP_PORT) as server:
        if settings.SMTP_TLS:
            server.starttls()
        server.login(user, password)
        server.send_message(message)
    return True


async def send_email(to_email: str, subject: str, html_content: str, plain_content: str | None = None) -> bool:
    try:
        return await asyncio.to_thread(_send_email_sync, to_email, subject, html_content, plain_content)
    except Exception:
        logger.exception("Lỗi gửi email tới %s", to_email)
        return False
