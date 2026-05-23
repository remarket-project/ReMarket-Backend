"""seed static content for help and legal pages

Revision ID: 20260523sc01
Revises: d42d9cf0b040
Create Date: 2026-05-23 00:00:01.000000

"""
from datetime import datetime, timezone
import uuid

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260523sc01'
down_revision = 'd42d9cf0b040'
branch_labels = None
depends_on = None


STATIC_CONTENT_ROWS = [
    {
        "id": uuid.UUID("8a8f5c39-5d66-4df2-b35c-5f2c4a5d1001"),
        "key": "help_home",
        "title": "Trợ giúp ReMarket",
        "body": "Trang trợ giúp tập trung cho người mua, người bán và người dùng mới.\n\nBạn có thể tìm câu trả lời nhanh theo các nhóm:\n- Mua hàng và thương lượng\n- Đăng và quản lý tin\n- Ví, escrow và thanh toán\n- Giao nhận, hoàn tiền và khiếu nại\n\nNếu chưa tìm thấy nội dung phù hợp, hãy xem mục Liên hệ để gửi yêu cầu hỗ trợ.",
        "locale": "vi",
        "version": 1,
    },
    {
        "id": uuid.UUID("8a8f5c39-5d66-4df2-b35c-5f2c4a5d1002"),
        "key": "help_buying",
        "title": "Hướng dẫn mua hàng",
        "body": "1. Tìm sản phẩm theo danh mục, từ khóa hoặc bộ lọc giá.\n2. Mở trang chi tiết để xem ảnh, mô tả, vị trí và độ uy tín của người bán.\n3. Dùng Chat để hỏi thêm hoặc gửi Offer nếu muốn thương lượng giá.\n4. Chọn Mua ngay nếu muốn chốt đơn nhanh.\n5. Theo dõi đơn hàng trong tab Đơn hàng và thanh toán qua escrow để an toàn hơn.",
        "locale": "vi",
        "version": 1,
    },
    {
        "id": uuid.UUID("8a8f5c39-5d66-4df2-b35c-5f2c4a5d1003"),
        "key": "help_selling",
        "title": "Hướng dẫn bán hàng",
        "body": "1. Tạo bài đăng với tiêu đề rõ ràng, ảnh thật và mô tả đầy đủ.\n2. Chọn danh mục đúng để bài đăng dễ được tìm thấy.\n3. Theo dõi trạng thái duyệt bài đăng trước khi hiển thị công khai.\n4. Trả lời tin nhắn và yêu cầu mua kịp thời để tăng tỉ lệ chốt đơn.\n5. Cập nhật đơn hàng, escrow và trạng thái hoàn tất đúng quy trình.",
        "locale": "vi",
        "version": 1,
    },
    {
        "id": uuid.UUID("8a8f5c39-5d66-4df2-b35c-5f2c4a5d1004"),
        "key": "help_payment",
        "title": "Thanh toán và ví",
        "body": "ReMarket dùng ví và escrow để giảm rủi ro trong giao dịch.\n\n- Người mua nạp tiền vào ví trước khi xác nhận thanh toán.\n- Khi đơn hàng hợp lệ, tiền được khóa vào escrow.\n- Người bán chỉ nhận tiền khi đơn hàng hoàn tất hoặc được admin xử lý hợp lệ.\n- Lịch sử giao dịch luôn hiển thị trong trang Ví.",
        "locale": "vi",
        "version": 1,
    },
    {
        "id": uuid.UUID("8a8f5c39-5d66-4df2-b35c-5f2c4a5d1005"),
        "key": "help_shipping",
        "title": "Giao nhận và theo dõi đơn",
        "body": "Đơn hàng đi theo các mốc chính: chờ xác nhận, xác nhận, giao hàng, đã giao và hoàn tất.\n\nHãy giữ liên hệ trong chat để thống nhất thời gian giao, điểm nhận hàng và tình trạng sản phẩm.\nNếu có thay đổi quan trọng, cập nhật ngay để tránh phát sinh tranh chấp.",
        "locale": "vi",
        "version": 1,
    },
    {
        "id": uuid.UUID("8a8f5c39-5d66-4df2-b35c-5f2c4a5d1006"),
        "key": "help_dispute",
        "title": "Khiếu nại và tranh chấp",
        "body": "Nếu giao dịch có vấn đề, bạn có thể mở tranh chấp từ trang đơn hàng hoặc escrow.\n\nNội dung nên cung cấp:\n- Lý do rõ ràng\n- Ảnh chụp màn hình hoặc bằng chứng liên quan\n- Thời điểm phát sinh vấn đề\n\nAdmin sẽ xem xét và xử lý theo trạng thái tiền đang giữ trong escrow.",
        "locale": "vi",
        "version": 1,
    },
    {
        "id": uuid.UUID("8a8f5c39-5d66-4df2-b35c-5f2c4a5d1007"),
        "key": "faq",
        "title": "Câu hỏi thường gặp",
        "body": "Q: Tôi có thể lưu tin và theo dõi người bán không?\nA: Có. Bạn có thể lưu bài đăng và theo dõi shop ngay trong giao diện.\n\nQ: Có thể thương lượng giá không?\nA: Có, nếu người bán bật trạng thái có thể thương lượng.\n\nQ: Tiền có an toàn không?\nA: Giao dịch đi qua ví và escrow để giảm rủi ro thanh toán.",
        "locale": "vi",
        "version": 1,
    },
    {
        "id": uuid.UUID("8a8f5c39-5d66-4df2-b35c-5f2c4a5d1008"),
        "key": "contact",
        "title": "Liên hệ hỗ trợ",
        "body": "Khi cần hỗ trợ, hãy liên hệ qua:\n- Email: support@remarket.local\n- Thời gian hỗ trợ: 08:00 - 18:00, Thứ 2 đến Thứ 6\n- Mô tả rõ vấn đề, kèm mã đơn hàng hoặc liên kết tin nếu có\n\nChúng tôi ưu tiên phản hồi các vấn đề liên quan đến thanh toán, tranh chấp và tài khoản.",
        "locale": "vi",
        "version": 1,
    },
    {
        "id": uuid.UUID("8a8f5c39-5d66-4df2-b35c-5f2c4a5d1009"),
        "key": "terms",
        "title": "Điều khoản sử dụng",
        "body": "1. Bạn phải cung cấp thông tin chính xác khi đăng ký và giao dịch.\n2. Không đăng tải nội dung vi phạm pháp luật, xâm phạm quyền riêng tư hoặc gây hiểu nhầm.\n3. ReMarket có quyền tạm ẩn, từ chối hoặc khóa nội dung/tài khoản vi phạm.\n4. Người dùng chịu trách nhiệm với nội dung, hàng hóa và thỏa thuận của mình.\n5. Các thay đổi điều khoản sẽ được cập nhật tại trang này.",
        "locale": "vi",
        "version": 1,
    },
    {
        "id": uuid.UUID("8a8f5c39-5d66-4df2-b35c-5f2c4a5d1010"),
        "key": "privacy",
        "title": "Chính sách quyền riêng tư",
        "body": "1. Chúng tôi chỉ thu thập dữ liệu cần thiết để vận hành tài khoản và giao dịch.\n2. Dữ liệu có thể bao gồm thông tin hồ sơ, lịch sử mua bán, nhắn tin và thanh toán.\n3. Thông tin chỉ được dùng cho mục đích vận hành, hỗ trợ và an toàn nền tảng.\n4. Chúng tôi không bán dữ liệu cá nhân cho bên thứ ba.\n5. Bạn có thể yêu cầu chỉnh sửa hoặc xóa dữ liệu theo chính sách hỗ trợ.",
        "locale": "vi",
        "version": 1,
    },
    {
        "id": uuid.UUID("8a8f5c39-5d66-4df2-b35c-5f2c4a5d1011"),
        "key": "cookies",
        "title": "Chính sách cookies",
        "body": "Chúng tôi sử dụng cookies và lưu trữ cục bộ để:\n- Ghi nhớ đăng nhập\n- Duy trì phiên làm việc\n- Cải thiện trải nghiệm tìm kiếm và điều hướng\n- Đo lường hiệu năng và sửa lỗi\n\nBạn có thể xoá cookies trong trình duyệt, nhưng một số tính năng đăng nhập có thể bị ảnh hưởng.",
        "locale": "vi",
        "version": 1,
    },
    {
        "id": uuid.UUID("8a8f5c39-5d66-4df2-b35c-5f2c4a5d1012"),
        "key": "community_guidelines",
        "title": "Nguyên tắc cộng đồng",
        "body": "Hãy giữ ReMarket là nơi mua bán an toàn, rõ ràng và tôn trọng.\n\n- Không spam, lừa đảo hoặc đăng tin giả.\n- Không đăng nội dung thô tục, bạo lực, kích động hoặc phân biệt đối xử.\n- Không sử dụng thông tin của người khác khi chưa được cho phép.\n- Hãy giao tiếp lịch sự và xác nhận thông tin trước khi giao dịch.",
        "locale": "vi",
        "version": 1,
    },
    {
        "id": uuid.UUID("8a8f5c39-5d66-4df2-b35c-5f2c4a5d1013"),
        "key": "refund_policy",
        "title": "Chính sách hoàn tiền",
        "body": "Hoàn tiền được xem xét khi:\n- Đơn hàng bị hủy đúng quy trình\n- Tranh chấp được admin kết luận hoàn tiền\n- Giao dịch không thể tiếp tục theo điều kiện escrow\n\nThời gian xử lý phụ thuộc vào trạng thái đơn hàng, bằng chứng và xác minh từ admin.",
        "locale": "vi",
        "version": 1,
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    content_table = sa.table(
        "static_contents",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("title", sa.String()),
        sa.column("body", sa.Text()),
        sa.column("locale", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    existing_keys = {
        row[0]
        for row in conn.execute(
            sa.select(content_table.c.key).where(
                content_table.c.locale == "vi")
        ).all()
    }

    now = datetime.now(timezone.utc)
    rows_to_insert = [
        {
            **row,
            "created_at": now,
            "updated_at": now,
        }
        for row in STATIC_CONTENT_ROWS
        if row["key"] not in existing_keys
    ]

    if rows_to_insert:
        op.bulk_insert(content_table, rows_to_insert)


def downgrade() -> None:
    conn = op.get_bind()
    keys = [row["key"] for row in STATIC_CONTENT_ROWS]
    conn.execute(
        sa.text(
            "DELETE FROM static_contents WHERE locale = :locale AND key = ANY(:keys)"
        ),
        {"locale": "vi", "keys": keys},
    )
