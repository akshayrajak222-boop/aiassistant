"""
OpenAI provider implementation.

Uses the official `openai` Python SDK with:
  - Streaming via SSE
  - Function / tool calling
  - Exponential-backoff retry on rate-limit / transient errors (tenacity)
  - Token usage logged to ProviderUsage table after every call
  - Embedding support via text-embedding-3-small (configurable)
"""

from __future__ import annotations

import logging
import os
import ssl
import time
from typing import Any, AsyncIterator

import httpx
import openai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from backend.providers.base import AIProvider

logger = logging.getLogger(__name__)

# ─── Retry policy ────────────────────────────────────────────────────────────

_RETRYABLE = (
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.InternalServerError,
)

_retry_policy = dict(
    retry=retry_if_exception_type(_RETRYABLE),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=3),
    stop=stop_after_attempt(3),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert provider-agnostic tool schemas → OpenAI function calling format."""
    result = []
    for tool in tools:
        result.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get(
                        "parameters", {"type": "object", "properties": {}}
                    ),
                },
            }
        )
    return result


def _convert_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pass messages through; map 'tool' role to OpenAI format."""
    converted = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("system", "user", "assistant"):
            converted.append({"role": role, "content": content})
        elif role == "tool":
            converted.append(
                {
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id", ""),
                    "content": content,
                }
            )
    return converted


async def _log_usage(
    user_id: str | None,
    model: str,
    operation: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float | None,
    conversation_id: str | None = None,
    task_id: str | None = None,
    error: str | None = None,
) -> None:
    """Persist a ProviderUsage record (fire-and-forget, never raises)."""
    try:
        from backend.database.session import AsyncSessionLocal
        from backend.database.models import ProviderUsage

        async with AsyncSessionLocal() as session:
            record = ProviderUsage(
                user_id=user_id,
                provider="openai",
                model=model,
                operation=operation,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                latency_ms=latency_ms,
                conversation_id=conversation_id,
                task_id=task_id,
                error=error,
            )
            session.add(record)
            await session.commit()
    except Exception:
        logger.exception("Failed to log provider usage (non-critical)")


class OpenAIProvider(AIProvider):
    """OpenAI GPT provider.

    Configuration (environment variables):
        OPENAI_API_KEY        – required; OpenAI API key.
        OPENAI_MODEL          – optional; chat model (default: gpt-4o).
        OPENAI_EMBED_MODEL    – optional; embedding model (default: text-embedding-3-small).
        OPENAI_MAX_TOKENS     – optional; max tokens per response (default: 4096).
        OPENAI_BASE_URL       – optional; custom base URL for Azure OpenAI etc.
    """

    _DEFAULT_MODEL = "gpt-4o"
    _DEFAULT_EMBED_MODEL = "text-embedding-3-small"
    _DEFAULT_MAX_TOKENS = 4096

    def __init__(self) -> None:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAIProvider")

        base_url = os.environ.get("OPENAI_BASE_URL") or None
        self._base_url = base_url

        # Ensure TLS 1.3 is configured to avoid Windows TLS renegotiation issues with Google endpoints
        ctx = ssl.create_default_context()
        try:
            ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        except AttributeError:
            pass

        http_client = httpx.AsyncClient(verify=ctx, timeout=60.0)
        self._client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        model_from_env = os.environ.get("OPENAI_MODEL") or os.environ.get("AI_MODEL")
        if not model_from_env or model_from_env in ("gpt-4o", "gemini-1.5-flash", "gemini-3.5-flash"):
            if base_url and "googleapis.com" in base_url:
                model_from_env = "gemini-3.5-flash-lite"
            else:
                model_from_env = model_from_env or self._DEFAULT_MODEL
        self._default_model = model_from_env
        self._embed_model = os.environ.get("OPENAI_EMBED_MODEL", self._DEFAULT_EMBED_MODEL)
        self._max_tokens = int(os.environ.get("OPENAI_MAX_TOKENS", str(self._DEFAULT_MAX_TOKENS)))

        logger.info("OpenAIProvider initialised | default_model=%s", self._default_model)

    # ------------------------------------------------------------------ #
    #  Base-class contract                                                  #
    # ------------------------------------------------------------------ #

    @property
    def name(self) -> str:
        return "openai"

    def supports_tools(self) -> bool:
        return True

    def supports_streaming(self) -> bool:
        return True

    # ------------------------------------------------------------------ #
    #  Streaming chat                                                       #
    # ------------------------------------------------------------------ #

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream chat completion via OpenAI SSE."""
        resolved_model = model or self._default_model
        if self._base_url and "googleapis.com" in self._base_url:
            if resolved_model in ("gpt-4o", "gemini-1.5-flash", "gemini-3.5-flash", None):
                resolved_model = "gemini-3.5-flash-lite"
        converted = _convert_messages(messages)
        openai_tools = _convert_tools(tools) if tools else openai.NOT_GIVEN  # type: ignore[attr-defined]

        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "max_tokens": self._max_tokens,
            "messages": converted,
            "stream": True,
        }
        if not (self._base_url and "googleapis.com" in self._base_url):
            kwargs["stream_options"] = {"include_usage": True}
        if tools:
            kwargs["tools"] = openai_tools

        input_tokens = 0
        output_tokens = 0
        t0 = time.monotonic()
        error_str: str | None = None

        @retry(**_retry_policy)
        async def _do_stream() -> AsyncIterator[str]:
            nonlocal input_tokens, output_tokens
            stream = await self._client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content
                # Capture final usage from the last chunk
                if hasattr(chunk, "usage") and chunk.usage:
                    input_tokens = chunk.usage.prompt_tokens
                    output_tokens = chunk.usage.completion_tokens

        try:
            async for chunk in _do_stream():
                yield chunk
        except openai.AuthenticationError:
            raise
        except Exception as exc:
            error_str = str(exc)
            logger.exception("OpenAI streaming error")
            raise
        finally:
            latency_ms = (time.monotonic() - t0) * 1000
            await _log_usage(
                user_id=None,
                model=resolved_model,
                operation="chat_stream",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                error=error_str,
            )

    # ------------------------------------------------------------------ #
    #  Non-streaming chat                                                  #
    # ------------------------------------------------------------------ #

    @retry(**_retry_policy)
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> str:
        """Non-streaming chat completion."""
        resolved_model = model or self._default_model
        if self._base_url and "googleapis.com" in self._base_url:
            if resolved_model in ("gpt-4o", "gemini-1.5-flash", "gemini-3.5-flash", None):
                resolved_model = "gemini-3.5-flash-lite"
        converted = _convert_messages(messages)
        openai_tools = _convert_tools(tools) if tools else openai.NOT_GIVEN  # type: ignore[attr-defined]

        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "max_tokens": self._max_tokens,
            "messages": converted,
        }
        if tools:
            kwargs["tools"] = openai_tools

        t0 = time.monotonic()
        error_str: str | None = None
        response = None

        try:
            response = await self._client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except openai.AuthenticationError:
            raise
        except Exception as exc:
            error_str = str(exc)
            logger.exception("OpenAI chat error")
            raise
        finally:
            latency_ms = (time.monotonic() - t0) * 1000
            input_tokens = 0
            output_tokens = 0
            if response and response.usage:
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
            await _log_usage(
                user_id=None,
                model=resolved_model,
                operation="chat",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                error=error_str,
            )

    # ------------------------------------------------------------------ #
    #  Embeddings                                                          #
    # ------------------------------------------------------------------ #

    @retry(**_retry_policy)
    async def embed(self, text: str) -> list[float]:
        """Generate an embedding vector using OpenAI's embedding API."""
        response = await self._client.embeddings.create(
            model=self._embed_model,
            input=text,
        )
        return response.data[0].embedding
