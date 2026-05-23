import logging
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.core.security import get_password_hash
from app.models import User, Category, StaticContent, UserRole

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


STATIC_CONTENT_SEED_DATA = [
    {
        "key": "help_home",
        "title": "Trợ giúp ReMarket",
        "body": """
Trang trợ giúp tập trung cho người mua, người bán và người dùng mới.

Bạn có thể tìm câu trả lời nhanh theo các nhóm:
- Mua hàng và thương lượng
- Đăng và quản lý tin
- Ví, escrow và thanh toán
- Giao nhận, hoàn tiền và khiếu nại

Nếu chưa tìm thấy nội dung phù hợp, hãy xem mục Liên hệ để gửi yêu cầu hỗ trợ.
""".strip(),
    },
    {
        "key": "help_buying",
        "title": "Hướng dẫn mua hàng",
        "body": """
1. Tìm sản phẩm theo danh mục, từ khóa hoặc bộ lọc giá.
2. Mở trang chi tiết để xem ảnh, mô tả, vị trí và độ uy tín của người bán.
3. Dùng Chat để hỏi thêm hoặc gửi Offer nếu muốn thương lượng giá.
4. Chọn Mua ngay nếu muốn chốt đơn nhanh.
5. Theo dõi đơn hàng trong tab Đơn hàng và thanh toán qua escrow để an toàn hơn.
""".strip(),
    },
    {
        "key": "help_selling",
        "title": "Hướng dẫn bán hàng",
        "body": """
1. Tạo bài đăng với tiêu đề rõ ràng, ảnh thật và mô tả đầy đủ.
2. Chọn danh mục đúng để bài đăng dễ được tìm thấy.
3. Theo dõi trạng thái duyệt bài đăng trước khi hiển thị công khai.
4. Trả lời tin nhắn và yêu cầu mua kịp thời để tăng tỉ lệ chốt đơn.
5. Cập nhật đơn hàng, escrow và trạng thái hoàn tất đúng quy trình.
""".strip(),
    },
    {
        "key": "help_payment",
        "title": "Thanh toán và ví",
        "body": """
ReMarket dùng ví và escrow để giảm rủi ro trong giao dịch.

- Người mua nạp tiền vào ví trước khi xác nhận thanh toán.
- Khi đơn hàng hợp lệ, tiền được khóa vào escrow.
- Người bán chỉ nhận tiền khi đơn hàng hoàn tất hoặc được admin xử lý hợp lệ.
- Lịch sử giao dịch luôn hiển thị trong trang Ví.
""".strip(),
    },
    {
        "key": "help_shipping",
        "title": "Giao nhận và theo dõi đơn",
        "body": """
Đơn hàng đi theo các mốc chính: chờ xác nhận, xác nhận, giao hàng, đã giao và hoàn tất.

Hãy giữ liên hệ trong chat để thống nhất thời gian giao, điểm nhận hàng và tình trạng sản phẩm.
Nếu có thay đổi quan trọng, cập nhật ngay để tránh phát sinh tranh chấp.
""".strip(),
    },
    {
        "key": "help_dispute",
        "title": "Khiếu nại và tranh chấp",
        "body": """
Nếu giao dịch có vấn đề, bạn có thể mở tranh chấp từ trang đơn hàng hoặc escrow.

Nội dung nên cung cấp:
- Lý do rõ ràng
- Ảnh chụp màn hình hoặc bằng chứng liên quan
- Thời điểm phát sinh vấn đề

Admin sẽ xem xét và xử lý theo trạng thái tiền đang giữ trong escrow.
""".strip(),
    },
    {
        "key": "faq",
        "title": "Câu hỏi thường gặp",
        "body": """
Q: Tôi có thể lưu tin và theo dõi người bán không?
A: Có. Bạn có thể lưu bài đăng và theo dõi shop ngay trong giao diện.

Q: Có thể thương lượng giá không?
A: Có, nếu người bán bật trạng thái có thể thương lượng.

Q: Tiền có an toàn không?
A: Giao dịch đi qua ví và escrow để giảm rủi ro thanh toán.
""".strip(),
    },
    {
        "key": "contact",
        "title": "Liên hệ hỗ trợ",
        "body": """
Khi cần hỗ trợ, hãy liên hệ qua:
- Email: support@remarket.local
- Thời gian hỗ trợ: 08:00 - 18:00, Thứ 2 đến Thứ 6
- Mô tả rõ vấn đề, kèm mã đơn hàng hoặc liên kết tin nếu có

Chúng tôi ưu tiên phản hồi các vấn đề liên quan đến thanh toán, tranh chấp và tài khoản.
""".strip(),
    },
    {
        "key": "terms",
        "title": "Điều khoản sử dụng",
        "body": """
1. Bạn phải cung cấp thông tin chính xác khi đăng ký và giao dịch.
2. Không đăng tải nội dung vi phạm pháp luật, xâm phạm quyền riêng tư hoặc gây hiểu nhầm.
3. ReMarket có quyền tạm ẩn, từ chối hoặc khóa nội dung/tài khoản vi phạm.
4. Người dùng chịu trách nhiệm với nội dung, hàng hóa và thỏa thuận của mình.
5. Các thay đổi điều khoản sẽ được cập nhật tại trang này.
""".strip(),
    },
    {
        "key": "privacy",
        "title": "Chính sách quyền riêng tư",
        "body": """
1. Chúng tôi chỉ thu thập dữ liệu cần thiết để vận hành tài khoản và giao dịch.
2. Dữ liệu có thể bao gồm thông tin hồ sơ, lịch sử mua bán, nhắn tin và thanh toán.
3. Thông tin chỉ được dùng cho mục đích vận hành, hỗ trợ và an toàn nền tảng.
4. Chúng tôi không bán dữ liệu cá nhân cho bên thứ ba.
5. Bạn có thể yêu cầu chỉnh sửa hoặc xóa dữ liệu theo chính sách hỗ trợ.
""".strip(),
    },
    {
        "key": "cookies",
        "title": "Chính sách cookies",
        "body": """
Chúng tôi sử dụng cookies và lưu trữ cục bộ để:
- Ghi nhớ đăng nhập
- Duy trì phiên làm việc
- Cải thiện trải nghiệm tìm kiếm và điều hướng
- Đo lường hiệu năng và sửa lỗi

Bạn có thể xoá cookies trong trình duyệt, nhưng một số tính năng đăng nhập có thể bị ảnh hưởng.
""".strip(),
    },
    {
        "key": "community_guidelines",
        "title": "Nguyên tắc cộng đồng",
        "body": """
Hãy giữ ReMarket là nơi mua bán an toàn, rõ ràng và tôn trọng.

- Không spam, lừa đảo hoặc đăng tin giả.
- Không đăng nội dung thô tục, bạo lực, kích động hoặc phân biệt đối xử.
- Không sử dụng thông tin của người khác khi chưa được cho phép.
- Hãy giao tiếp lịch sự và xác nhận thông tin trước khi giao dịch.
""".strip(),
    },
    {
        "key": "refund_policy",
        "title": "Chính sách hoàn tiền",
        "body": """
Hoàn tiền được xem xét khi:
- Đơn hàng bị hủy đúng quy trình
- Tranh chấp được admin kết luận hoàn tiền
- Giao dịch không thể tiếp tục theo điều kiện escrow

Thời gian xử lý phụ thuộc vào trạng thái đơn hàng, bằng chứng và xác minh từ admin.
""".strip(),
    },
]


def _upsert_static_content(session: Session, item: dict) -> None:
    existing = session.exec(
        select(StaticContent).where(
            StaticContent.key == item["key"],
            StaticContent.locale == "vi",
        )
    ).first()

    if not existing:
        content = StaticContent(
            key=item["key"],
            title=item["title"],
            body=item["body"],
            locale="vi",
            version=1,
        )
        session.add(content)
        logger.info(f"Created static content: {item['key']}")
        return

    if existing.title != item["title"] or existing.body != item["body"]:
        existing.title = item["title"]
        existing.body = item["body"]
        existing.version = (existing.version or 1) + 1
        existing.updated_at = datetime.now(timezone.utc)
        session.add(existing)
        logger.info(f"Updated static content: {item['key']}")


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
        # Seed Categories (flat structure - 8 categories)
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
        # Seed Static Content (Help + Legal)
        # ====================================================================
        for content_item in STATIC_CONTENT_SEED_DATA:
            _upsert_static_content(session, content_item)

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
