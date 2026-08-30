import asyncio
import json
import logging
from typing import Any

import httpx
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.exceptions import AllModelsExhaustedError, RateLimitError
from app.core.quota_tracker import quota_tracker

logger = logging.getLogger(__name__)

_GEMINI_SEMAPHORE = asyncio.Semaphore(5)


class AIClient:

    def __init__(self):
        self._gemini_clients: dict[str, Any] = {}
        self._nine_router_client: AsyncOpenAI | None = None
        self._local_embed_model = None
        self._embed_cache: dict[str, list[float]] = {}

    # ─── Chat (9Router → Gemini → AllModelsExhausted) ────────────

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> str:
        # 1. Thử 9Router trước (nếu có cấu hình)
        if settings.NINE_ROUTER_BASE_URL and settings.NINE_ROUTER_CHAT_MODEL:
            try:
                return await self._nine_router_chat(messages, tools)
            except Exception as e:
                logger.warning("9Router failed: %s — fallback to Gemini", e)

        # 2. Fallback Gemini (multi-key + multi-model rotation)
        api_keys = self._get_api_keys()
        if not api_keys:
            logger.warning("No GEMINI_API_KEYS configured")
            raise AllModelsExhaustedError("No API keys configured")

        models = settings.GEMINI_CHAT_MODELS
        last_error: Exception | None = None

        for model in models:
            for api_key in api_keys:
                if not quota_tracker.can_use(api_key, model):
                    continue

                try:
                    async with _GEMINI_SEMAPHORE:
                        result = await self._gemini_chat(api_key, model, messages, tools)
                    quota_tracker.increment(api_key, model)
                    return result
                except RateLimitError as e:
                    quota_tracker.record_error(api_key, model)
                    logger.warning(
                        "Rate limited: %s / %s — rotating",
                        quota_tracker.key_for_log(api_key), model,
                    )
                    last_error = e
                    continue
                except Exception as e:
                    logger.error(
                        "Gemini error on %s / %s: %s",
                        quota_tracker.key_for_log(api_key), model, e,
                    )
                    last_error = e
                    continue

        raise AllModelsExhaustedError(last_error)

    # ─── 9Router (OpenAI-compatible) ────────────────────────────

    async def _nine_router_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> str:
        """Gọi 9Router với combo ReMarket_chatbot (Antigravity free models)."""
        client = self._get_nine_router_client()

        # Convert tools từ Gemini format → OpenAI format
        openai_tools = None
        if tools:
            openai_tools = [{"type": "function", "function": t} for t in tools]

        # Convert messages: model role → assistant role
        openai_messages = []
        for msg in messages:
            role = "assistant" if msg["role"] == "model" else msg["role"]
            openai_messages.append({"role": role, "content": msg["content"]})

        response = await client.chat.completions.create(  # type: ignore
            model=settings.NINE_ROUTER_CHAT_MODEL,
            messages=openai_messages,
            tools=openai_tools,
            temperature=0.7,
            max_tokens=1024,
        )

        choice = response.choices[0]

        # Tool call → convert về function_call format (tương thích faq_chatbot)
        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            tc = choice.message.tool_calls[0]
            return json.dumps({
                "function_call": {
                    "name": tc.function.name,
                    "args": json.loads(tc.function.arguments),
                }
            })

        return choice.message.content or ""

    def _get_nine_router_client(self) -> AsyncOpenAI:
        if self._nine_router_client is None:
            self._nine_router_client = AsyncOpenAI(
                base_url=settings.NINE_ROUTER_BASE_URL,
                api_key=settings.NINE_ROUTER_API_KEY or "sk-9router",
                timeout=httpx.Timeout(30.0, connect=5.0),
            )
        return self._nine_router_client

    def _get_api_keys(self) -> list[str]:
        keys = settings.GEMINI_API_KEYS
        if keys:
            return keys
        if settings.GEMINI_API_KEY:
            return [settings.GEMINI_API_KEY]
        return []

    async def _gemini_chat(
        self,
        api_key: str,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> str:
        from google.genai import types  # type: ignore[import-untyped]

        client = self._get_gemini_client(api_key)

        contents = []
        system_msg = None
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
                continue
            role = "user" if msg["role"] in ("user", "model") else "user"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        config_kwargs = {}
        if tools:
            config_kwargs["tools"] = [
                types.Tool(function_declarations=tools)
            ]
        if system_msg:
            config_kwargs["system_instruction"] = system_msg

        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(**config_kwargs),  # type: ignore[arg-type]
            )
        except Exception as e:
            err_str = str(e).lower()
            if any(kw in err_str for kw in ["429", "rate limit", "quota", "too many", "resource exhausted", "403", "permission"]):
                raise RateLimitError(str(e)) from e
            raise

        if not response.candidates:
            return "Xin lỗi, tôi không thể xử lý yêu cầu này."
        if response.candidates[0].content.parts:
            part = response.candidates[0].content.parts[0]
            if part.function_call:
                return json.dumps({
                    "function_call": {
                        "name": part.function_call.name,
                        "args": dict(part.function_call.args.items()),
                    }
                })

        return str(response.text or "")

    def _get_gemini_client(self, api_key: str):
        if api_key not in self._gemini_clients:
            from google import genai  # type: ignore[import-untyped]
            self._gemini_clients[api_key] = genai.Client(api_key=api_key)
        return self._gemini_clients[api_key]

    # ─── Embed (local sentence-transformers + cache) ─────────

    @retry(stop=stop_after_attempt(settings.AI_MAX_RETRIES),
           wait=wait_exponential(multiplier=1, min=2, max=10))
    async def embed(self, texts: list[str], prefix: str = "") -> list[list[float]]:
        if not texts:
            return []

        # Dùng Gemini API làm Cloud Embedding (0 MB RAM, không cần sentence-transformers)
        if settings.AI_PROVIDER == "gemini":
            from google.genai import types  # type: ignore[import-untyped]
            api_keys = self._get_api_keys()
            if not api_keys:
                raise ValueError("GEMINI_API_KEY is not configured for embedding")
            api_key = api_keys[0]
            client = self._get_gemini_client(api_key)
            
            formatted_texts = [f"{prefix}{t}" for t in texts] if prefix else texts
            
            # Thử gemini-embedding-2 trước, fallback sang gemini-embedding-001 (khống chế 768 chiều)
            for model_name in ["gemini-embedding-2", "gemini-embedding-001"]:
                try:
                    response = await client.aio.models.embed_content(
                        model=model_name,
                        contents=formatted_texts,
                        config=types.EmbedContentConfig(
                            output_dimensionality=768
                        )
                    )
                    return [emb.values for emb in response.embeddings]
                except Exception as e:
                    logger.warning("Gemini embed failed with %s: %s, trying fallback...", model_name, e)
                    continue
            
            raise RuntimeError("All Gemini embedding models failed")

        # Mặc định: Dùng local model (sentence-transformers)
        try:
            if prefix:
                texts = [f"{prefix}{t}" for t in texts]
            model = self._get_local_embed_model()
            loop = asyncio.get_running_loop()
            embeddings = await loop.run_in_executor(
                None,
                lambda: model.encode(texts, show_progress_bar=False, normalize_embeddings=True).tolist(),
            )
            return embeddings  # type: ignore[no-any-return]
        except (ModuleNotFoundError, ImportError) as e:
            logger.warning("sentence-transformers not installed; local embedding unavailable")
            return []
        except Exception as e:
            logger.warning("Local embedding generation failed: %s", e)
            return []

    async def embed_one(self, text: str, prefix: str = "") -> list[float]:
        cache_key = f"{prefix}|{text}" if prefix else text
        cached = self._embed_cache.get(cache_key)
        if cached is not None:
            return cached
        result = await self.embed([text], prefix=prefix)
        vec = result[0] if result else []
        if vec:
            self._embed_cache[cache_key] = vec
        return vec

    def _get_local_embed_model(self):
        if self._local_embed_model is None:
            try:
                from sentence_transformers import (  # type: ignore[import-untyped]
                    SentenceTransformer,
                )
                logger.info("Loading embed model: %s", settings.LOCAL_EMBED_MODEL)
                self._local_embed_model = SentenceTransformer(settings.LOCAL_EMBED_MODEL)
            except ImportError:
                logger.warning("sentence-transformers not installed; local embedding unavailable")
                raise
            except Exception as e:
                logger.critical("Failed to load embedding model '%s': %s", settings.LOCAL_EMBED_MODEL, e)
                raise
        return self._local_embed_model


ai_client = AIClient()
