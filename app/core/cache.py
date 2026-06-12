from cachetools import TTLCache

# Cache instances cho các loại data khác nhau
category_cache = TTLCache(maxsize=100, ttl=300)       # 5 phút cho category
stats_cache = TTLCache(maxsize=10, ttl=30)            # 30 giây cho dashboard stats
price_band_cache = TTLCache(maxsize=20, ttl=60)       # 1 phút cho price bands
content_cache = TTLCache(maxsize=50, ttl=600)          # 10 phút cho static content
