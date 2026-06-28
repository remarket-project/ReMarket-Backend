from __future__ import annotations

import json
import logging
import random
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlmodel import Session, select
from sqlalchemy import text as sa_text

from app.core.db import engine
from app.models import (
    Category,
    ConditionGrade,
    Listing,
    ListingImage,
    ListingStatus,
    User,
    UserRole,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VND_RATE = 25000
PRODUCTS_PER_USER = 4

EN_TO_VN = {
    # Brands
    "Apple": "Apple", "Samsung": "Samsung", "Nike": "Nike",
    "Dell": "Dell", "HP": "HP", "Sony": "Sony", "Xiaomi": "Xiaomi",
    "Puma": "Puma", "Adidas": "Adidas", "Rolex": "Rolex",
    "IWC": "IWC", "Amazon": "Amazon", "Google": "Google",
    "LG": "LG", "Tissot": "Tissot", "Citizen": "Citizen",
    "Canon": "Canon", "Yamaha": "Yamaha", "Bosch": "Bosch",
    "Philips": "Philips", "Lego": "Lego", "JBL": "JBL",
    "Honda": "Honda", "Toyota": "Toyota", "VinFast": "VinFast",
    "Louis": "Louis", "Vuitton": "Vuitton", "Gucci": "Gucci",
    # Electronics
    "Laptop": "Laptop", "Smartphone": "Điện thoại", "Phone": "Điện thoại",
    "Tablet": "Máy tính bảng", "iPad": "iPad", "iPhone": "iPhone",
    "MacBook": "MacBook", "Watch": "Đồng hồ", "Camera": "Máy ảnh",
    "Headphones": "Tai nghe", "Earbuds": "Tai nghe",
    "Charger": "Sạc", "Cable": "Cáp", "Keyboard": "Bàn phím",
    "Mouse": "Chuột", "Monitor": "Màn hình", "Speaker": "Loa",
    "Echo": "Echo", "Alexa": "Alexa", "Kindle": "Kindle",
    "Fire": "Fire", "Pro": "Pro", "Air": "Air",
    "Galaxy": "Galaxy", "Note": "Note",
    # Fashion
    "Shirt": "Áo sơ mi", "Shirts": "Áo sơ mi",
    "T-Shirt": "Áo thun", "T-Shirts": "Áo thun",
    "Jacket": "Áo khoác", "Jackets": "Áo khoác",
    "Coat": "Áo khoác", "Dress": "Váy", "Dresses": "Váy",
    "Shoes": "Giày", "Shoe": "Giày", "Sneakers": "Giày thể thao",
    "Boots": "Ủng", "Sandals": "Dép", "Heels": "Giày cao gót",
    "Bag": "Túi xách", "Bags": "Túi xách", "Backpack": "Balo",
    "Handbag": "Túi xách", "Wallet": "Ví", "Belt": "Thắt lưng",
    "Sunglasses": "Kính mát", "Glasses": "Kính",
    "Watch": "Đồng hồ", "Watches": "Đồng hồ",
    "Jewellery": "Trang sức", "Jewelry": "Trang sức",
    "Necklace": "Dây chuyền", "Ring": "Nhẫn", "Earring": "Hoa tai",
    "Bracelet": "Vòng tay", "Earrings": "Hoa tai",
    "Top": "Áo", "Tops": "Áo", "Blouse": "Áo blouse",
    "Pant": "Quần", "Pants": "Quần", "Jeans": "Quần jean",
    "Short": "Quần short", "Shorts": "Quần short",
    "Skirt": "Chân váy", "Suit": "Bộ vest",
    "Tie": "Cà vạt", "Scarf": "Khăn",
    # Colors
    "Black": "Đen", "White": "Trắng", "Red": "Đỏ",
    "Blue": "Xanh", "Green": "Xanh lá", "Yellow": "Vàng",
    "Pink": "Hồng", "Purple": "Tím", "Brown": "Nâu",
    "Grey": "Xám", "Gray": "Xám", "Gold": "Vàng",
    "Silver": "Bạc", "Orange": "Cam",
    # Furniture
    "Chair": "Ghế", "Table": "Bàn", "Desk": "Bàn làm việc",
    "Bed": "Giường", "Sofa": "Sofa", "Cabinet": "Tủ",
    "Shelf": "Kệ", "Shelves": "Kệ", "Lamp": "Đèn",
    "Mirror": "Gương", "Rug": "Thảm", "Curtain": "Rèm",
    "Cushion": "Đệm", "Pillow": "Gối",
    "Decoration": "Trang trí", "Decor": "Trang trí",
    "Vase": "Bình hoa", "Frame": "Khung", "Candle": "Nến",
    "Plant": "Cây", "Flower": "Hoa",
    # Kitchen
    "Knife": "Dao", "Knives": "Bộ dao", "Pan": "Chảo",
    "Pot": "Nồi", "Bowl": "Bát", "Plate": "Đĩa",
    "Cup": "Cốc", "Glass": "Ly", "Bottle": "Chai",
    "Jar": "Hũ", "Spatula": "Spát", "Peeler": "Đồ gọt vỏ",
    "Slicer": "Máy thái", "Grater": "Máy bào", "Sieve": "Rây",
    "Strainer": "Lọc", "Oven": "Lò nướng", "Microwave": "Lò vi sóng",
    "Blender": "Máy xay", "Toaster": "Máy nướng bánh",
    "Cooker": "Nồi cơm", "Kettle": "Ấm đun nước",
    "Coffee": "Cà phê", "Maker": "Máy pha", "Machine": "Máy",
    # Sports
    "Ball": "Bóng", "Football": "Bóng đá", "Basketball": "Bóng rổ",
    "Baseball": "Bóng chày", "Volleyball": "Bóng chuyền",
    "Racket": "Vợt", "Racquet": "Vợt", "Bat": "Gậy",
    "Glove": "Găng tay", "Helmet": "Mũ bảo hiểm",
    "Shoe": "Giày", "Shoes": "Giày",
    "Gym": "Phòng gym", "Fitness": "Thể hình",
    "Yoga": "Yoga", "Mat": "Thảm",
    "Bicycle": "Xe đạp", "Bike": "Xe đạp",
    "Accessory": "Phụ kiện", "Accessories": "Phụ kiện",
    # Vehicle
    "Motorcycle": "Xe máy", "Car": "Xe hơi", "Vehicle": "Xe",
    "Tire": "Lốp", "Wheel": "Bánh xe", "Engine": "Động cơ",
    "Brake": "Phanh", "Light": "Đèn", "Seat": "Ghế",
    "Battery": "Bình ắc quy", "Filter": "Lọc",
    # Beauty
    "Mascara": "Mascara", "Lipstick": "Son môi",
    "Foundation": "Kem nền", "Powder": "Phấn phủ",
    "Eyeshadow": "Phấn mắt", "Nail": "Móng tay",
    "Polish": "Sơn", "Perfume": "Nước hoa",
    "Fragrance": "Hương thơm", "Scent": "Mùi hương",
    "Cream": "Kem", "Lotion": "Sữa dưỡng", "Oil": "Dầu",
    "Serum": "Serum", "Mask": "Mặt nạ", "Soap": "Xà phòng",
    "Shampoo": "Dầu gội", "Conditioner": "Dầu xả",
    # Gender
    "Women": "Nữ", "Women's": "Nữ",
    "Men": "Nam", "Men's": "Nam",
    "Mens": "Nam", "Womens": "Nữ",
    "Male": "Nam", "Female": "Nữ",
    "Unisex": "Unisex",
    "Man": "Nam", "Woman": "Nữ",
    # Descriptors
    "New": "Mới", "Old": "Cũ", "Vintage": "Cổ điển",
    "Modern": "Hiện đại", "Classic": "Cổ điển",
    "Premium": "Cao cấp", "Luxury": "Sang trọng",
    "Elegant": "Thanh lịch", "Stylish": "Phong cách",
    "Comfortable": "Thoải mái", "Portable": "Di động",
    "Wireless": "Không dây", "Bluetooth": "Bluetooth",
    "Smart": "Thông minh", "Digital": "Kỹ thuật số",
    "Automatic": "Tự động", "Manual": "Thủ công",
    "Large": "Lớn", "Small": "Nhỏ", "Medium": "Vừa",
    "Extra": "Siêu", "Ultra": "Siêu",
    "Lightweight": "Nhẹ", "Durable": "Bền",
    "Waterproof": "Chống nước", "Stainless": "Không gỉ",
    "Steel": "Thép", "Leather": "Da", "Wood": "Gỗ",
    "Plastic": "Nhựa", "Metal": "Kim loại",
    "Cotton": "Vải cotton", "Silk": "Lụa", "Wool": "Len",
    "Crystal": "Pha lê", "Diamond": "Kim cương",
    "Gold": "Vàng", "Silver": "Bạc",
    "Stainless Steel": "Thép không gỉ",
    "Folding": "Gấp gọn", "Adjustable": "Có thể điều chỉnh",
    "Rechargeable": "Có thể sạc", "Portable": "Di động",
    # General goods
    "Product": "Sản phẩm", "Set": "Bộ", "Kit": "Bộ",
    "Pack": "Gói", "Box": "Hộp", "Case": "Hộp",
    "Bag": "Túi", "Bags": "Túi",
    "Toy": "Đồ chơi", "Toys": "Đồ chơi",
    "Game": "Trò chơi", "Console": "Máy chơi game",
    "Book": "Sách", "Books": "Sách",
    "Pen": "Bút", "Pencil": "Bút chì",
    "Paper": "Giấy", "Notebook": "Vở",
    # Numbers/measurements
    "Inch": "inch", "Inches": "inch",
    "mm": "mm", "cm": "cm", "m": "m", "kg": "kg", "g": "g",
    "ml": "ml", "L": "L",
    "Watt": "W", "Volt": "V",
}

DUMMYJSON_CATEGORIES: dict[str, str] = {
    "laptops": "dien-tu-cong-nghe",
    "smartphones": "dien-tu-cong-nghe",
    "tablets": "dien-tu-cong-nghe",
    "mobile-accessories": "dien-tu-cong-nghe",
    "mens-shirts": "thoi-trang",
    "mens-shoes": "thoi-trang",
    "mens-watches": "thoi-trang",
    "womens-bags": "thoi-trang",
    "womens-dresses": "thoi-trang",
    "womens-jewellery": "thoi-trang",
    "womens-shoes": "thoi-trang",
    "womens-watches": "thoi-trang",
    "tops": "thoi-trang",
    "sunglasses": "thoi-trang",
    "kitchen-accessories": "do-gia-dung",
    "sports-accessories": "do-the-thao",
    "furniture": "noi-that",
    "home-decoration": "noi-that",
    "motorcycle": "xe-co",
    "vehicle": "xe-co",
    "beauty": "khac",
    "fragrances": "khac",
    "skin-care": "khac",
}

OUR_CATEGORIES = [
    "dien-tu-cong-nghe",
    "thoi-trang",
    "do-gia-dung",
    "do-the-thao",
    "noi-that",
    "xe-co",
    "khac",
]

CATEGORY_DESC = {
    "dien-tu-cong-nghe": "Sản phẩm công nghệ đã qua sử dụng, hoạt động tốt.",
    "thoi-trang": "Thời trang second-hand chất lượng, phong cách đa dạng.",
    "do-gia-dung": "Đồ gia dụng còn tốt, giá tốt cho gia đình.",
    "do-the-thao": "Dụng cụ thể thao đã qua sử dụng, chất lượng còn tốt.",
    "noi-that": "Nội thất đẹp, phù hợp cho căn hộ và văn phòng.",
    "xe-co": "Xe cộ và phụ tùng đã qua sử dụng, còn hoạt động tốt.",
    "khac": "Sản phẩm đa dạng, chất lượng tốt, giá hợp lý.",
}

TITLE_OVERRIDES: dict[str, str] = {
    "Samsung Galaxy S23": "Samsung Galaxy S23 Plus",
    "iPhone 5s": "iPhone 5s",
    "iPhone 6": "iPhone 6",
    "iPhone X": "iPhone X",
    "iPhone XS Max": "iPhone XS Max",
    "Apple MacBook Pro 14 Inch Space Grey": "MacBook Pro 14 inch Xám",
    "New DELL XPS 13 9300 Laptop": "Dell XPS 13 9300 Laptop",
    "Asus Zenbook Pro Dual Screen Laptop": "Asus Zenbook Pro Màn hình Kép",
    "Huawei Matebook X Pro": "Huawei Matebook X Pro",
    "Lenovo Yoga 920": "Lenovo Yoga 920",
    "Apple AirPods Wireless Bluetooth Headphones": "AirPods Tai nghe Bluetooth",
    "Samsung Galaxy Tab S8 Plus High Resolution": "Samsung Galaxy Tab S8 Plus",
    "Samsung Galaxy Tab": "Samsung Galaxy Tab",
    "Samsung Universe 9": "Samsung Universe 9",
    "Apple iPhone 12": "Apple iPhone 12",
    "Apple iPhone 12 Mini": "Apple iPhone 12 Mini",
    "Blue Women's Handbag": "Túi xách nữ màu xanh",
    "Green Women's Handbag": "Túi xách nữ màu xanh lá",
    "Women Handbag Black": "Túi xách nữ màu đen",
    "White Women's Handbag": "Túi xách nữ màu trắng",
    "Green Oval Earring": "Hoa tai hình bầu dục xanh",
    "Pearl Earring": "Hoa tai ngọc trai",
    "Red Nail Polish": "Sơn móng tay đỏ",
    "Black Nail Polish": "Sơn móng tay đen",
    "Egg Slicer": "Dụng cụ thái trứng",
    "Boxed Blender": "Máy xay sinh tố",
    "Granny Smith Apple": "Táo xanh Granny Smith",
    "Apple Cider Vinegar": "Dấm táo",
    "Táo HomePod Mini": "Apple HomePod Mini",
    "Táo iPhone 12": "Apple iPhone 12",
    "Táo iPhone 12 Mini": "Apple iPhone 12 Mini",
}

CATEGORY_VN = {
    "dien-tu-cong-nghe": "Điện tử & Công nghệ",
    "thoi-trang": "Thời trang",
    "do-gia-dung": "Đồ gia dụng",
    "do-the-thao": "Đồ thể thao",
    "noi-that": "Nội thất",
    "xe-co": "Xe cộ",
    "khac": "Khác",
}


def to_vietnamese(text: str) -> str:
    if text in TITLE_OVERRIDES:
        return TITLE_OVERRIDES[text]

    words = text.split()
    result: list[str] = []
    skip_next = False
    for i, w in enumerate(words):
        if skip_next:
            skip_next = False
            continue
        cleaned = w.strip(".,()[]{}!?\"'")
        punct_before = w[:len(w) - len(cleaned)] if cleaned else ""
        punct_after = w[len(cleaned):] if cleaned else ""
        core = cleaned

        core_lower = core.lower()
        if core_lower == "mens":
            translated = "Nam"
        elif core_lower in ("womens", "women's", "women"):
            translated = "Nữ"
        else:
            translated = EN_TO_VN.get(core, core)
            if translated == core:
                translated = EN_TO_VN.get(core.capitalize(), core)

        result.append(punct_before + translated + punct_after)
    vn_text = " ".join(result)
    vn_text = vn_text.replace("Táo ", "Apple ").replace("Táo", "Apple", 1)
    return vn_text


def generate_vn_description(
    vn_title: str,
    en_description: str,
    our_category: str,
    rng: random.Random,
) -> str:
    templates = [
        f"{vn_title} chất lượng tốt, đã qua sử dụng cẩn thận. {rng.choice(['Phù hợp sử dụng hàng ngày.', 'Còn rất tốt, ít sử dụng.', 'Đã được vệ sinh sạch sẽ.', 'Hoạt động ổn định, không vấn đề.'])}",
        CATEGORY_DESC.get(our_category, "Sản phẩm chất lượng, giá tốt."),
    ]
    return templates[0]


@dataclass
class DummyProduct:
    title_en: str
    title_vn: str
    description_en: str
    description_vn: str
    price_usd: float
    images: list[str]
    our_category: str


def fetch_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def fetch_all_products(rng: random.Random) -> list[DummyProduct]:
    data = fetch_json("https://dummyjson.com/products?limit=200")
    products: list[DummyProduct] = []
    for p in data["products"]:
        dj_cat = p.get("category", "")
        our_cat = DUMMYJSON_CATEGORIES.get(dj_cat)
        if not our_cat:
            continue
        images = p.get("images", [])
        if not images:
            continue
        title_en = p["title"]
        title_vn = to_vietnamese(title_en)
        desc_en = p.get("description", "")
        desc_vn = generate_vn_description(title_vn, desc_en, our_cat, rng)
        products.append(DummyProduct(
            title_en=title_en,
            title_vn=title_vn,
            description_en=desc_en,
            description_vn=desc_vn,
            price_usd=p.get("price", 0),
            images=images,
            our_category=our_cat,
        ))
    logger.info("Fetched %s products from DummyJSON", len(products))
    return products


def seed_realistic() -> None:
    rng = random.Random()

    products = fetch_all_products(rng)

    products_by_cat: dict[str, list[DummyProduct]] = {}
    for p in products:
        products_by_cat.setdefault(p.our_category, []).append(p)

    for cat in OUR_CATEGORIES:
        count = len(products_by_cat.get(cat, []))
        logger.info("  %s: %s products", cat, count)

    valid_categories = [c for c in OUR_CATEGORIES if products_by_cat.get(c)]

    with Session(engine) as session:
        slug_to_cat: dict[str, Category] = {
            c.slug: c for c in session.exec(select(Category)).all()
        }

        missing = [c for c in valid_categories if c not in slug_to_cat]
        if missing:
            logger.error("Missing categories in DB: %s", missing)
            return

        users = session.exec(
            select(User).where(User.role == UserRole.USER)
        ).all()
        logger.info("Found %s regular users", len(users))

        total_listings = 0
        total_images = 0
        users_skipped = 0

        for user in users:
            existing = session.exec(
                select(Listing).where(Listing.seller_id == user.id)
            ).all()
            if len(existing) >= 3:
                users_skipped += 1
                continue

            for i in range(PRODUCTS_PER_USER):
                cat_slug = valid_categories[i % len(valid_categories)]
                cat_products = products_by_cat[cat_slug]
                p = rng.choice(cat_products)

                condition = rng.choice([
                    ConditionGrade.LIKE_NEW,
                    ConditionGrade.GOOD,
                    ConditionGrade.FAIR,
                ])

                price_vnd = int(p.price_usd * VND_RATE * rng.uniform(0.7, 1.0))
                price_vnd = max(price_vnd, 20000)

                listing = Listing(
                    title=p.title_vn,
                    description=p.description_vn,
                    price=Decimal(price_vnd).quantize(Decimal("0.01")),
                    is_negotiable=rng.choice([True, True, False]),
                    condition_grade=condition,
                    status=ListingStatus.ACTIVE,
                    seller_id=user.id,
                    category_id=slug_to_cat[cat_slug].id,
                    published_at=datetime.now(timezone.utc),
                )
                session.add(listing)
                session.flush()

                for j, url in enumerate(p.images[:3]):
                    img = ListingImage(
                        listing_id=listing.id,
                        image_url=url,
                        is_primary=(j == 0),
                    )
                    session.add(img)
                    total_images += 1

                total_listings += 1

        session.commit()
        logger.info("Seed complete")
        logger.info("Users processed: %s", len(users))
        logger.info("Users skipped: %s", users_skipped)
        logger.info("Listings created: %s", total_listings)
        logger.info("Images created: %s", total_images)


def main() -> None:
    seed_realistic()


if __name__ == "__main__":
    main()
