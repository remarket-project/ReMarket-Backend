from dataclasses import dataclass


@dataclass
class ProductSeed:
    title: str
    description: str
    price_vnd: int
    image_urls: list[str]


def _url(photo_id: str) -> str:
    if photo_id.startswith("http"):
        return photo_id
    return f"https://unsplash.com/photos/{photo_id}/download?force=true"


SEED_DATA: dict[str, list[ProductSeed]] = {}


SEED_DATA["dien-tu-cong-nghe"] = [
    ProductSeed(
        title="MacBook Pro M2 2023 - 14 inch",
        description="Máy tính xách tay Apple MacBook Pro M2 2023, màn hình 14 inch, RAM 16GB, SSD 512GB. Máy còn rất mới, pin trên 90%, đầy đủ phụ kiện kèm theo.",
        price_vnd=28000000,
        image_urls=[
            _url("1611186871348-b1ce696e52c9"),
            _url("xII7efH1G6o"),
        ],
    ),
    ProductSeed(
        title="iPhone 14 Pro Max 256GB",
        description="iPhone 14 Pro Max màu tím, dung lượng 256GB, máy như mới, full box, chưa thay pin, còn bảo hành đến 12/2024.",
        price_vnd=22000000,
        image_urls=[_url("1611186871348-b1ce696e52c9")],
    ),
    ProductSeed(
        title="Tai nghe Sony WH-1000XM5",
        description="Tai nghe chống ồn chủ động Sony WH-1000XM5, màu đen, chống ồn cực tốt, pin trâu 30h, đầy đủ phụ kiện. Dùng được 3 tháng.",
        price_vnd=4500000,
        image_urls=[
            _url("1611235224327-1b7dda8d4e1f"),
            _url("xII7efH1G6o"),
        ],
    ),
    ProductSeed(
        title="Máy ảnh Canon EOS R50 + Lens Kit",
        description="Máy ảnh mirrorless Canon EOS R50 kèm lens 18-45mm, chụp ảnh đẹp, quay video 4K. Máy mới mua 3 tháng, ít sử dụng.",
        price_vnd=15000000,
        image_urls=[_url("nimElTcTNyY")],
    ),
    ProductSeed(
        title="Đồng hồ thông minh Apple Watch Series 9",
        description="Apple Watch Series 9 45mm viền nhôm dây silicone màu xanh, pin tốt, đầy đủ tính năng sức khỏe. Đã dùng 2 tháng.",
        price_vnd=8500000,
        image_urls=[
            _url("1523275335684-7b300c81d6a7"),
            _url("K0DxxljcRv0"),
        ],
    ),
]

SEED_DATA["thoi-trang"] = [
    ProductSeed(
        title="Áo khoác trenchcoat màu be",
        description="Áo khoác dáng dài màu be phong cách Hàn Quốc, chất liệu cotton cao cấp, form rộng. Mặc 2 lần, còn rất mới.",
        price_vnd=650000,
        image_urls=[
            _url("nimElTcTNyY"),
            _url("_3Q3tsJ01nc"),
        ],
    ),
    ProductSeed(
        title="Túi xách da thật cao cấp",
        description="Túi xách nữ da bò thật, màu nâu vintage, khóa kim loại sang trọng. Túi rộng rãi, phù hợp đi làm và đi chơi.",
        price_vnd=1200000,
        image_urls=[
            _url("BteCp6aq4GI"),
            _url("TS--uNw-JqE"),
        ],
    ),
    ProductSeed(
        title="Giày sneakers nam nữ Uniqlo",
        description="Giày sneakers trắng phong cách tối giản, đi êm chân, phù hợp mọi trang phục. Size 39-42. Còn 90%.",
        price_vnd=450000,
        image_urls=[
            _url("dwKiHoqqxk8"),
            _url("BTuUO8o2iK4"),
        ],
    ),
    ProductSeed(
        title="Đồng hồ nam Citizen Eco-Drive",
        description="Đồng hồ nam Citizen dây thép không gỉ, mặt số xanh, năng lượng ánh sáng, chống nước 100m. Full box, còn mới.",
        price_vnd=3500000,
        image_urls=[
            _url("1523275335684-7b300c81d6a7"),
        ],
    ),
    ProductSeed(
        title="Kính mát Rayban Aviator",
        description="Kính mát Rayban Aviator phiên bản classic, gọng vàng, tròng xanh, chống tia UV. Hàng authentic, có hộp đựng.",
        price_vnd=2800000,
        image_urls=[
            _url("PKMvkg7vnUo"),
            _url("OVS3rqXq9gg"),
        ],
    ),
]

SEED_DATA["do-gia-dung"] = [
    ProductSeed(
        title="Máy pha cà phê Philips Series 2200",
        description="Máy pha cà phê tự động Philips Series 2200, pha được nhiều loại cà phê, bình chứa 1.8L, đã vệ sinh sạch sẽ.",
        price_vnd=5500000,
        image_urls=[
            _url("wkC8EX8y9Mc"),
            _url("MP0bgaS_d1c"),
        ],
    ),
    ProductSeed(
        title="Nồi chiên không dầu 5.5L",
        description="Nồi chiên không dầu dung tích 5.5L, công suất 1500W, điều khiển kỹ thuật số, 8 chế độ nấu. Còn mới 90%.",
        price_vnd=950000,
        image_urls=[
            _url("tzwERVbuRYQ"),
            _url("ovEBmY4HxPM"),
        ],
    ),
    ProductSeed(
        title="Máy hút bụi không dây Xiaomi G9",
        description="Máy hút bụi cầm tay không dây Xiaomi G9, lực hút mạnh 25kPa, pin liền 45 phút, có đèn LED. Đầy đủ phụ kiện.",
        price_vnd=3200000,
        image_urls=[_url("wkC8EX8y9Mc")],
    ),
    ProductSeed(
        title="Bộ dao nhà bếp Đức 5 món",
        description="Bộ dao nhà bếp 5 món thương hiệu Đức, lưỡi thép không gỉ, tay cầm gỗ óc chó, có kệ đựng. Rất sắc bén.",
        price_vnd=1800000,
        image_urls=[_url("MP0bgaS_d1c")],
    ),
    ProductSeed(
        title="Ấm siêu tốc 1.7L LocknLock",
        description="Ấm đun nước siêu tốc LocknLock 1.7L, vỏ inox 304, đáy rộng nhanh sôi, tự ngắt điện. Dùng 6 tháng.",
        price_vnd=350000,
        image_urls=[
            _url("tzwERVbuRYQ"),
        ],
    ),
]

SEED_DATA["do-the-thao"] = [
    ProductSeed(
        title="Giày chạy bộ Nike Pegasus 40",
        description="Giày chạy bộ Nike Air Zoom Pegasus 40, màu xanh đen, size 42. Đế chạy êm, đã chạy khoảng 100km, còn 80%.",
        price_vnd=1800000,
        image_urls=[
            _url("ugZxwLQuZec"),
            _url("RPVspeDIxXI"),
        ],
    ),
    ProductSeed(
        title="Xe đạp đua roadbike 700C",
        description="Xe đạp đua đường trường 700C, khung hợp kim nhôm, bộ đề Shimano Sora 9-speed, phanh đĩa. Xe đẹp, chạy tốt.",
        price_vnd=7500000,
        image_urls=[
            _url("E0OeYD_iMA4"),
        ],
    ),
    ProductSeed(
        title="Bóng đá Nike Premier League",
        description="Bóng đá Nike Premier League size 5, da PU cao cấp, chuẩn FIFA, từng dùng 5 trận. Kèm bơm và túi đựng.",
        price_vnd=550000,
        image_urls=[
            _url("BTuUO8o2iK4"),
        ],
    ),
    ProductSeed(
        title="Vợt tennis Wilson Pro Staff",
        description="Vợt tennis Wilson Pro Staff mới 95%, dây đánh tốt, có túi đựng. Phù hợp người chơi trung cấp trở lên.",
        price_vnd=2200000,
        image_urls=[
            _url("dwKiHoqqxk8"),
        ],
    ),
    ProductSeed(
        title="Bộ tạ tập gym 20kg",
        description="Bộ tạ đơn tháo lắp 20kg (2 tạ x 10kg), tay cầm chống trượt, mạ crom chống gỉ. Kèm giá đỡ.",
        price_vnd=1200000,
        image_urls=[
            _url("RPVspeDIxXI"),
            _url("ugZxwLQuZec"),
        ],
    ),
]

SEED_DATA["noi-that"] = [
    ProductSeed(
        title="Bàn làm việc gỗ công nghiệp 1m2",
        description="Bàn làm việc gỗ công nghiệp MDF, mặt bàn trắng, chân sắt đen, kích thước 120x60x75cm. Còn mới nguyên.",
        price_vnd=1500000,
        image_urls=[
            _url("ovEBmY4HxPM"),
        ],
    ),
    ProductSeed(
        title="Ghế văn phòng Ergonomic",
        description="Ghế văn phòng lưng lưới cao cấp, tựa đầu, xoay, nâng hạ. Phù hợp làm việc 8 tiếng. Còn 85%.",
        price_vnd=2800000,
        image_urls=[
            _url("MP0bgaS_d1c"),
            _url("wkC8EX8y9Mc"),
        ],
    ),
    ProductSeed(
        title="Kệ sách 3 tầng gỗ tự nhiên",
        description="Kệ sách 3 tầng gỗ thông tự nhiên, màu nâu vàng, kích thước 80x30x120cm. Chịu lực tốt, đẹp và bền.",
        price_vnd=1200000,
        image_urls=[
            _url("1583394833488-f7f5e22c33c2"),
        ],
    ),
    ProductSeed(
        title="Đèn bàn học LED chống mỏi mắt",
        description="Đèn bàn LED Philips, ánh sáng trung tính, chống nhấp nháy, 3 chế độ sáng, có cổng sạc USB. Dùng 2 tháng.",
        price_vnd=650000,
        image_urls=[
            _url("tzwERVbuRYQ"),
        ],
    ),
    ProductSeed(
        title="Sofa mini 2 chỗ ngồi",
        description="Sofa mini 2 chỗ vải nỉ cao cấp, xanh rêu, khung gỗ chắc chắn. Sofa nhỏ gọn, phù hợp căn hộ chung cư.",
        price_vnd=4500000,
        image_urls=[
            _url("ovEBmY4HxPM"),
            _url("MP0bgaS_d1c"),
        ],
    ),
]

SEED_DATA["sach-hoc-lieu"] = [
    ProductSeed(
        title="Sách 'Đắc Nhân Tâm' bản tiếng Việt",
        description="Sách Đắc Nhân Tâm của Dale Carnegie, bản tiếng Việt, NXB Tổng Hợp. Sách còn mới, chưa ghi chú.",
        price_vnd=85000,
        image_urls=[
            _url("1583394833488-f7f5e22c33c2"),
        ],
    ),
    ProductSeed(
        title="Bộ bút lông màu 36 màu",
        description="Bộ bút lông màu nước 36 màu, đầu nhỏ phù hợp tô màu và vẽ kỹ thuật. Hàng Nhật, mới 80%.",
        price_vnd=250000,
        image_urls=[
            _url("1583394833488-f7f5e22c33c2"),
        ],
    ),
    ProductSeed(
        title="Vở ghi chép bìa cứng A5",
        description="Vở ghi chép bìa cứng A5, 200 trang, giấy kem, không lem mực. Bộ 3 quyển. Còn nguyên seal.",
        price_vnd=90000,
        image_urls=[
            _url("QAqbUDp00PY"),
        ],
    ),
    ProductSeed(
        title="Balô học sinh Jansport",
        description="Balô Jansport chính hãng, màu đen, nhiều ngăn chứa, chống nước, quai đeo êm. Đã dùng học 1 kỳ, còn 90%.",
        price_vnd=750000,
        image_urls=[
            _url("1473188018185-9c1c3535e6db"),
        ],
    ),
    ProductSeed(
        title="iPad Gen 10 64GB Wifi",
        description="iPad thế hệ 10 64GB Wifi, màu hồng, kèm bút cảm ứng. Máy còn mới, pin ổn. Học online giải trí tuyệt vời.",
        price_vnd=9500000,
        image_urls=[
            _url("1611186871348-b1ce696e52c9"),
        ],
    ),
]

SEED_DATA["xe-co"] = [
    ProductSeed(
        title="Xe máy Wave Alpha 110cc 2022",
        description="Xe Wave Alpha màu đen bạc, 2022, số sàn, chạy 15.000km, giấy tờ đầy đủ. Xe tiết kiệm xăng, đi tốt.",
        price_vnd=15000000,
        image_urls=[
            _url("CCx6Fz_CmOI"),
        ],
    ),
    ProductSeed(
        title="Xe đạp điện VinFast Evo 200",
        description="Xe đạp điện VinFast Evo 200, pin lithium 48V, chạy 80km/lần sạc. Mới mua 3 tháng, có giấy mua bán.",
        price_vnd=18000000,
        image_urls=[
            _url("E0OeYD_iMA4"),
        ],
    ),
    ProductSeed(
        title="Camera hành trình ô tô Xiaomi 70mai",
        description="Camera hành trình Xiaomi 70mai A800, quay 4K, góc rộng, GPS tích hợp. Full hộp, còn mới nguyên.",
        price_vnd=2500000,
        image_urls=[
            _url("1611235224327-1b7dda8d4e1f"),
        ],
    ),
    ProductSeed(
        title="Mũ bảo hiểm fullface LS2",
        description="Mũ bảo hiểm fullface LS2, size M, kính chống trầy, quai khóa nhanh. Màu đen mờ. Phù hợp xe máy phân khối lớn.",
        price_vnd=1800000,
        image_urls=[
            _url("UqT55tGBqzI"),
        ],
    ),
    ProductSeed(
        title="Xe đạp địa hình MTB 27 bánh 27.5",
        description="Xe đạp địa hình MTB 27.5 inch, khung thép crom, bộ đề Shimano 21-speed, phanh đĩa. Còn 80%, đạp tốt.",
        price_vnd=3200000,
        image_urls=[
            _url("dlxLGIy-2VU"),
        ],
    ),
]

SEED_DATA["khac"] = [
    ProductSeed(
        title="Đàn guitar acoustic Yamaha F310",
        description="Guitar acoustic Yamaha F310, dây thép, mặt gỗ thông, cần đàn thẳng. Đàn còn mới, tiếng chuẩn. Kèm bao đàn.",
        price_vnd=2200000,
        image_urls=[
            _url("xXJ6utyoSw0"),
        ],
    ),
    ProductSeed(
        title="Máy chơi game PS5 Slim Digital",
        description="PS5 Slim Digital Edition, ổ SSD 1TB, kèm 1 tay cầm. Máy mới mua 2 tháng, ít chơi. Full box + hóa đơn.",
        price_vnd=9500000,
        image_urls=[
            _url("jaZoffxg1yc"),
        ],
    ),
    ProductSeed(
        title="Loa Bluetooth JBL Charge 5",
        description="Loa bluetooth JBL Charge 5, công suất 30W, pin 20h, chống nước IP67. Âm bass mạnh, sạc được điện thoại.",
        price_vnd=2500000,
        image_urls=[
            _url("qnKhZJPKFD8"),
            _url("mwa_nzFpnJw"),
        ],
    ),
    ProductSeed(
        title="Rượu vang Ý Fontanafredda 2018",
        description="Chai rượu vang đỏ Fontanafredda Barolo 2018, Ý. Rượu vintage, hương vị phức hợp. Chưa khui, còn nguyên tem.",
        price_vnd=1800000,
        image_urls=[
            _url("K0DxxljcRv0"),
        ],
    ),
    ProductSeed(
        title="Đồ chơi mô hình Lego Technic Porsche 911",
        description="Lego Technic Porsche 911 GT3 RS 42056, đầy đủ chi tiết và hộp. Đã lắp 1 lần, tháo ra để nguyên. Cực kỳ đẹp.",
        price_vnd=3500000,
        image_urls=[
            _url("PKMvkg7vnUo"),
            _url("OVS3rqXq9gg"),
        ],
    ),
]
