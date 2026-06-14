class RateLimitError(Exception):
    """Gemini rate limit / quota exceeded — sẽ rotate key/model."""
    pass


class AllModelsExhaustedError(Exception):
    """Tất cả cặp (key, model) từ tất cả tài khoản đều hết quota.
    Caller phải fallback sang RAG-only mode."""
    pass
