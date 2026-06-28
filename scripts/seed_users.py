import logging
from datetime import datetime, timezone

from sqlmodel import Session, create_engine, select

from app.core.config import settings
from app.core.security import get_password_hash
from app.models import User, UserRole

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

PASSWORD_HASH = get_password_hash("12345678")

users_data = [
    {"full_name": "Admin", "email": "admin@remarket.vn"},
    {"full_name": "HUNG", "email": "Hung@gmail.com"},
    {"full_name": "Admin", "email": "Admin@gmail.com"},
    {"full_name": "Nguyễn Văn An", "email": "nguyen.van.an@gmail.com"},
    {"full_name": "Trần Thị Bảo", "email": "tran.thi.bao@gmail.com"},
    {"full_name": "Lê Văn Cường", "email": "le.van.cuong@gmail.com"},
    {"full_name": "Phạm Thị Dung", "email": "pham.thi.dung@gmail.com"},
    {"full_name": "Hoàng Văn Em", "email": "hoang.van.em@gmail.com"},
    {"full_name": "Vũ Văn Giang", "email": "vu.van.giang@gmail.com"},
    {"full_name": "Đặng Thị Hạnh", "email": "dang.thi.hanh@gmail.com"},
    {"full_name": "Bùi Văn Hoàng", "email": "bui.van.hoang@gmail.com"},
    {"full_name": "Vương Thị Kiều", "email": "vuong.thi.kieu@gmail.com"},
    {"full_name": "Đỗ Văn Long", "email": "do.van.long@gmail.com"},
    {"full_name": "Lý Thị Mai", "email": "ly.thi.mai@gmail.com"},
    {"full_name": "Nguyễn Văn Mạnh", "email": "nguyen.van.manh@gmail.com"},
    {"full_name": "Trần Văn Nam", "email": "tran.van.nam@gmail.com"},
    {"full_name": "Phạm Văn Phi", "email": "pham.van.phi@gmail.com"},
    {"full_name": "Cao Thị Quế", "email": "cao.thi.que@gmail.com"},
    {"full_name": "Lý Văn Tâm", "email": "ly.van.tam@gmail.com"},
    {"full_name": "Trần Văn Thành", "email": "tran.van.thanh@gmail.com"},
    {"full_name": "Nguyễn Thị Tuyết", "email": "nguyen.thi.tuyet@gmail.com"},
    {"full_name": "Dương Văn Vượng", "email": "duong.van.vuong@gmail.com"},
    {"full_name": "Nguyễn Thị Phương", "email": "nguyen.thi.phuong@gmail.com"},
    {"full_name": "Phạm Thị Hồng", "email": "pham.thi.hong@gmail.com"},
    {"full_name": "Đinh Văn Hùng", "email": "dinh.van.hung@gmail.com"},
    {"full_name": "Võ Thị Lan", "email": "vo.thi.lan@gmail.com"},
    {"full_name": "Hồ Văn Đức", "email": "ho.van.duc@gmail.com"},
    {"full_name": "Lương Thị Thảo", "email": "luong.thi.thao@gmail.com"},
    {"full_name": "Mai Văn Tuấn", "email": "mai.van.tuan@gmail.com"},
    {"full_name": "Đào Thị Yến", "email": "dao.thi.yen@gmail.com"},
]

def main():
    with Session(engine) as session:
        # Delete ALL existing users first
        all_users = session.exec(select(User)).all()
        logger.info(f"Deleting {len(all_users)} existing users...")
        for u in all_users:
            session.delete(u)
        session.flush()
        logger.info("All existing users deleted")

        # Create 30 fresh users
        now = datetime.now(timezone.utc)
        created = 0

        for i, user in enumerate(users_data, start=1):
            new_user = User(
                email=user["email"],
                full_name=user["full_name"],
                password_hash=PASSWORD_HASH,
                role=UserRole.ADMIN if user["email"] in ("admin@remarket.vn", "Admin@gmail.com") else UserRole.USER,
                is_active=True,
                is_email_verified=True,
                is_phone_verified=True,
                phone=f"09{i:02d}{hash(user['email']) % 10000000:07d}",
                province="Hồ Chí Minh",
                district="Quận 1",
                ward="Phường Bến Nghé",
                address_detail=f"{i} Nguyễn Huệ, Quận 1",
                bio=f"Người dùng ReMarket - {user['full_name']}",
                trust_score=5.0,
                rating_avg=5.0,
                rating_count=0,
                completed_orders=0,
                created_at=now,
                updated_at=now,
            )
            session.add(new_user)
            created += 1
            logger.info(f"[{created}/30] Created: {user['email']} ({user['full_name']})")

        session.commit()
        logger.info(f"Done! Created {created} users")

if __name__ == "__main__":
    main()
