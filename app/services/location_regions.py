"""Ánh xạ tỉnh/thành phố Việt Nam sang 3 miền Bắc - Trung - Nam."""

NORTH_KEYWORDS = [
    "hà nội", "hanoi", "ha noi",
    "bắc ninh", "bắc giang", "bắc kạn", "bắc cạn",
    "hải phòng", "hải dương", "hưng yên",
    "quảng ninh", "thái nguyên", "phú thọ",
    "nam định", "thái bình", "vinh phúc", "vĩnh phúc",
    "tuyên quang", "hà giang", "lào cai",
    "lai châu", "điện biên", "sơn la", "hòa bình",
    "yên bái", "cao bằng", "lạng sơn",
    "ninh bình", "hà nam",
    "móng cái",
]

CENTRAL_KEYWORDS = [
    "đà nẵng", "da nang", "danang",
    "huế", "thừa thiên huế", "thừa thiên", "thua thien",
    "quảng trị", "quảng bình",
    "quảng nam", "quảng ngãi",
    "bình định", "phú yên",
    "khánh hòa", "nha trang",
    "ninh thuận", "bình thuận",
    "gia lai", "kon tum", "đắk lắk", "dak lak",
    "đắk nông", "dak nong", "lâm đồng", "đà lạt",
    "thanh hóa", "nghệ an", "hà tĩnh",
]

SOUTH_KEYWORDS = [
    "hồ chí minh", "hcmc", "hcm", "saigon", "sài gòn",
    "tp hcm", "tphcm", "ho chi minh",
    "bình dương", "đồng nai", "bà rịa", "vũng tàu",
    "tây ninh", "bình phước",
    "long an", "tiền giang", "bến tre", "trà vinh",
    "vĩnh long", "đồng tháp",
    "cần thơ", "hậu giang", "sóc trăng",
    "bạc liêu", "cà mau", "kiên giang", "an giang",
]


def get_region_keywords(region: str) -> list[str] | None:
    region = region.lower().strip()
    if region in ("north", "bắc", "bac", "hà nội", "hanoi", "ha noi"):
        return NORTH_KEYWORDS
    if region in ("central", "trung", "đà nẵng", "da nang", "danang"):
        return CENTRAL_KEYWORDS
    if region in ("south", "nam", "hồ chí minh", "hcmc", "hcm", "ho chi minh"):
        return SOUTH_KEYWORDS
    return None
