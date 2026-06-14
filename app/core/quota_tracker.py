import json
import logging
from datetime import date
from pathlib import Path
from threading import Lock

from app.core.config import settings

logger = logging.getLogger(__name__)

QUOTA_FILE = Path(__file__).resolve().parent.parent / "data" / "quota_usage.json"


class QuotaTracker:
    """
    Thread-safe quota tracker.

    Lưu trong file JSON để persist qua restart server.
    Reset counter mỗi ngày (dựa trên date).

    Cấu trúc file:
    {
        "date": "2026-06-14",
        "usage": {
            "key1_gemini-3.1-flash-lite": 5,
            ...
        },
        "errors": {
            "key1_gemini-3.1-flash-lite": 0,
            ...
        }
    }
    """

    def __init__(self):
        self._lock = Lock()
        self._data = self._load()

    def can_use(self, api_key: str, model: str) -> bool:
        """Kiểm tra cặp (key, model) còn quota không."""
        self._ensure_today()
        key = self._key(api_key, model)
        usage = self._data["usage"].get(key, 0)
        limit = self._get_limit(model)
        errors = self._data["errors"].get(key, 0)
        if errors >= 3:
            logger.warning("Key %s model %s tạm ngưng (>=3 lỗi 429)", self.key_for_log(api_key), model)
            return False
        if usage >= limit:
            return False
        # Cảnh báo sớm nếu gần hết quota
        threshold = settings.GEMINI_RPD_WARN_THRESHOLD
        if usage >= limit * threshold:
            logger.info("Key %s model %s: %d/%d RPD (gần hết)", self.key_for_log(api_key), model, usage, limit)
        return True

    def increment(self, api_key: str, model: str):
        """Tăng counter sau khi gọi Gemini thành công."""
        self._ensure_today()
        key = self._key(api_key, model)
        self._data["usage"][key] = self._data["usage"].get(key, 0) + 1
        self._save()

    def record_error(self, api_key: str, model: str):
        """Ghi nhận lỗi 429/403 cho cặp (key, model)."""
        self._ensure_today()
        key = self._key(api_key, model)
        self._data["errors"][key] = self._data["errors"].get(key, 0) + 1
        self._save()

    def get_usage_summary(self) -> dict:
        self._ensure_today()
        return {
            "date": self._data["date"],
            "usage": dict(self._data["usage"]),
            "errors": dict(self._data["errors"]),
        }

    def key_for_log(self, api_key: str) -> str:
        if len(api_key) > 8:
            return api_key[:4] + "..." + api_key[-4:]
        return "****"

    def _key(self, api_key: str, model: str) -> str:
        return f"{api_key}_{model}"

    def _get_limit(self, model: str) -> int:
        return settings.GEMINI_RPD_LIMITS.get(model, 20)

    def _ensure_today(self):
        today = date.today().isoformat()
        if self._data.get("date") != today:
            self._data = {"date": today, "usage": {}, "errors": {}}
            self._save()

    def _load(self) -> dict:
        try:
            if QUOTA_FILE.exists():
                with open(QUOTA_FILE, encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning("Failed to load quota file: %s", e)
        return {"date": date.today().isoformat(), "usage": {}, "errors": {}}

    def _save(self):
        try:
            QUOTA_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(QUOTA_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("Failed to save quota file: %s", e)


quota_tracker = QuotaTracker()
