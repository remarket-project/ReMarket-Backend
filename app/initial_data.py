import logging

from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.core.security import get_password_hash
from app.models import User, Category, UserRole

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db_data() -> None:
    """Initialize database with seed data."""
    with Session(engine) as session:
        # ====================================================================
        # Create Admin User (if not exists)
        # ====================================================================
        admin_user = session.exec(
            select(User).where(User.email == settings.FIRST_SUPERUSER)
        ).first()

        if not admin_user:
            admin_user = User(
                email=settings.FIRST_SUPERUSER,
                full_name="Admin",
                password_hash=get_password_hash(
                    settings.FIRST_SUPERUSER_PASSWORD),
                role=UserRole.ADMIN,
                is_active=True,
                is_email_verified=True,
            )
            session.add(admin_user)
            logger.info(f"Created admin user: {settings.FIRST_SUPERUSER}")

        # ====================================================================
        # Seed Categories (Root level - 8 categories)
        # ====================================================================
        categories_data = [
            {
                "name": "Điện tử & Công nghệ",
                "slug": "dien-tu-cong-nghe",
                "icon_url": "https://via.placeholder.com/64?text=Electronics",
            },
            {
                "name": "Thời trang",
                "slug": "thoi-trang",
                "icon_url": "https://via.placeholder.com/64?text=Fashion",
            },
            {
                "name": "Đồ gia dụng",
                "slug": "do-gia-dung",
                "icon_url": "https://via.placeholder.com/64?text=Home",
            },
            {
                "name": "Xe cộ",
                "slug": "xe-co",
                "icon_url": "https://via.placeholder.com/64?text=Vehicles",
            },
            {
                "name": "Sách & Học liệu",
                "slug": "sach-hoc-lieu",
                "icon_url": "https://via.placeholder.com/64?text=Books",
            },
            {
                "name": "Đồ thể thao",
                "slug": "do-the-thao",
                "icon_url": "https://via.placeholder.com/64?text=Sports",
            },
            {
                "name": "Nội thất",
                "slug": "noi-that",
                "icon_url": "https://via.placeholder.com/64?text=Furniture",
            },
            {
                "name": "Khác",
                "slug": "khac",
                "icon_url": "https://via.placeholder.com/64?text=Other",
            },
        ]

        for cat_data in categories_data:
            existing = session.exec(
                select(Category).where(Category.slug == cat_data["slug"])
            ).first()

            if not existing:
                category = Category(**cat_data)
                session.add(category)
                logger.info(f"Created category: {cat_data['name']}")

        # ====================================================================
        # Commit all changes
        # ====================================================================
        session.commit()
        logger.info("Database seed completed")


def main() -> None:
    logger.info("Creating initial data in database...")
    init_db_data()
    logger.info("Initial data seeded successfully!")


if __name__ == "__main__":
    main()
