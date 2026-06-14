"""
FAQ response cache.

Cache câu trả lời từ Gemini để giảm RPD usage cho câu hỏi trùng lặp.

Cache key: hash của câu hỏi (normalized — lowercase, trim)
Cache value: {"answer": str, "source": str | None, "mode": str}
TTL: 30 phút
Storage: in-memory dict (mất khi restart)

Invalidation:
- Khi chạy reindex_faq() → clear toàn bộ cache
"""

import hashlib
import logging
import time
from threading import Lock

logger = logging.getLogger(__name__)

DEFAULT_TTL = 1800
MAX_CACHE_SIZE = 500


class FaqCache:
    """
    Thread-safe FAQ response cache.
    TTL 30 phút. Không cache product search / trending.
    """

    def __init__(self, ttl: int = DEFAULT_TTL):
        self._ttl = ttl
        self._cache: dict[str, tuple[float, dict]] = {}
        self._lock = Lock()

    def get(self, question: str) -> dict | None:
        """Lấy cached response. None nếu miss hoặc expired."""
        key = self._normalize(question)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.time() > expires_at:
                del self._cache[key]
                return None
            return value

    def set(self, question: str, response: dict):
        """Cache response cho câu hỏi."""
        key = self._normalize(question)
        with self._lock:
            if len(self._cache) >= MAX_CACHE_SIZE:
                oldest = min(self._cache.items(), key=lambda x: x[1][0])
                del self._cache[oldest[0]]
            self._cache[key] = (time.time() + self._ttl, response)

    def clear(self):
        """Clear toàn bộ cache — gọi khi reindex FAQ."""
        with self._lock:
            self._cache.clear()
        logger.info("FAQ cache cleared")

    def stats(self) -> dict:
        with self._lock:
            return {
                "size": len(self._cache),
                "ttl": self._ttl,
                "max_size": MAX_CACHE_SIZE,
            }

    @staticmethod
    def _normalize(question: str) -> str:
        q = question.lower().strip()
        q = " ".join(q.split())
        return hashlib.md5(q.encode("utf-8")).hexdigest()


faq_cache = FaqCache()
