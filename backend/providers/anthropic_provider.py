"""
Anthropic provider implementation.

Uses the official `anthropic` Python SDK with:
  - Streaming via SSE
  - Tool/function calling (Claude tool use format)
  - Exponential-backoff retry on rate-limit / transient errors (tenacity)
  - Token usage logged to the ProviderUsage table after every call
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, AsyncIterator

import anthropic
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
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
)

_retry_policy = dict(
    retry=retry_if_exception_type(_RETRYABLE),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert provider-agnostic tool schemas → Anthropic tool format."""
    result = []
    for tool in tools:
        result.append(
            {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "input_schema": tool.get("parameters", tool.get("input_schema", {"type": "object", "properties": {}})),
            }
        )
    return result


def _convert_messages(messages: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
    """Split out any system message and convert the rest to Anthropic format."""
    system: str | None = None
    converted: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "system":
            system = content
        elif role in ("user", "assistant"):
            converted.append({"role": role, "content": content})
        elif role == "tool":
            # Tool result block expected by Anthropic
            converted.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.get("tool_call_id", ""),
                            "content": content,
                        }
                    ],
                }
            )

    return system, converted


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
                provider="anthropic",
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


class AnthropicProvider(AIProvider):
    """Anthropic Claude provider.

    Configuration (environment variables):
        ANTHROPIC_API_KEY   – required; Anthropic API key.
        ANTHROPIC_MODEL     – optional; default model (default: claude-3-5-sonnet-20241022).
        ANTHROPIC_MAX_TOKENS – optional; max tokens per response (default: 8192).
    """

    _DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
    _DEFAULT_MAX_TOKENS = 8192

    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required for AnthropicProvider")

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._sync_client = anthropic.Anthropic(api_key=api_key)
        self._default_model = os.environ.get("ANTHROPIC_MODEL", self._DEFAULT_MODEL)
        self._max_tokens = int(os.environ.get("ANTHROPIC_MAX_TOKENS", str(self._DEFAULT_MAX_TOKENS)))

        logger.info("AnthropicProvider initialised | default_model=%s", self._default_model)

    # ------------------------------------------------------------------ #
    #  Base-class contract                                                  #
    # ------------------------------------------------------------------ #

    @property
    def name(self) -> str:
        return "anthropic"

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
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream chat completion via Anthropic SSE."""
        resolved_model = model or self._default_model
        system, converted_messages = _convert_messages(messages)
        anthropic_tools = _convert_tools(tools) if tools else anthropic.NOT_GIVEN

        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "max_tokens": max_tokens or self._max_tokens,
            "messages": converted_messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = anthropic_tools

        input_tokens = 0
        output_tokens = 0
        t0 = time.monotonic()

        @retry(**_retry_policy)
        async def _do_stream() -> AsyncIterator[str]:
            nonlocal input_tokens, output_tokens

            async with self._client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_delta":
                            delta = event.delta
                            if hasattr(delta, "text") and delta.text:
                                yield delta.text
                        elif event.type == "message_delta" and hasattr(event, "usage"):
                            output_tokens = event.usage.output_tokens
                        elif event.type == "message_start" and hasattr(event, "message"):
                            if hasattr(event.message, "usage"):
                                input_tokens = event.message.usage.input_tokens

        try:
            async for chunk in _do_stream():
                yield chunk
        except anthropic.AuthenticationError as exc:
            logger.error("Anthropic auth error: %s", exc)
            raise
        except anthropic.BadRequestError as exc:
            logger.error("Anthropic bad request: %s", exc)
            raise
        except Exception as exc:
            logger.exception("Anthropic streaming error: %s", exc)
            await _log_usage(
                user_id=None,
                model=resolved_model,
                operation="chat_stream",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=(time.monotonic() - t0) * 1000,
                error=str(exc),
            )
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
        max_tokens: int | None = None,
    ) -> str:
        """Non-streaming chat completion."""
        resolved_model = model or self._default_model
        system, converted_messages = _convert_messages(messages)
        anthropic_tools = _convert_tools(tools) if tools else anthropic.NOT_GIVEN

        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "max_tokens": max_tokens or self._max_tokens,
            "messages": converted_messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = anthropic_tools

        t0 = time.monotonic()
        error_str: str | None = None

        try:
            response = await self._client.messages.create(**kwargs)
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text
            return text
        except anthropic.AuthenticationError:
            raise
        except Exception as exc:
            error_str = str(exc)
            logger.exception("Anthropic chat error")
            raise
        finally:
            latency_ms = (time.monotonic() - t0) * 1000
            input_tokens = 0
            output_tokens = 0
            try:
                # response may not be bound if the call failed
                input_tokens = response.usage.input_tokens  # type: ignore[possibly-undefined]
                output_tokens = response.usage.output_tokens  # type: ignore[possibly-undefined]
            except Exception:
                pass
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

    async def embed(self, text: str) -> list[float]:
        """Anthropic does not natively provide an embedding endpoint.

        Raises NotImplementedError – callers should fall back to OpenAI or
        another embedding provider when using Anthropic as the chat provider.
        """
        raise NotImplementedError(
            "AnthropicProvider does not support embeddings. "
            "Use OpenAI or a dedicated embedding provider."
        )
