"""
Ollama provider implementation.

Ollama exposes an OpenAI-compatible /v1 REST API which this provider targets.
The provider reuses the `openai` Python SDK pointed at the local Ollama server.

Configuration (environment variables):
    OLLAMA_BASE_URL – Base URL for the Ollama server (default: http://localhost:11434).
    OLLAMA_MODEL    – Default model to use (default: llama3.2).

NOTE on tool calling:
    Ollama supports tool calling only on specific models (e.g. llama3.1, mistral-nemo,
    qwen2.5, etc. with a native tool-calling architecture). Models that do not support
    tool calling will receive the tool schemas embedded in the system prompt as a JSON
    description, allowing the model to attempt tool use via text output, but with no
    guarantee of structured output. Callers should check `supports_tools()` against the
    specific model in use and degrade gracefully when tools are not natively supported.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, AsyncIterator

import openai

from backend.providers.base import AIProvider

logger = logging.getLogger(__name__)

# Models known to support native tool calling through Ollama's /v1 API.
# Note: 1B and 0.5B models lack capacity for tool calling and are excluded.
_TOOL_CAPABLE_MODELS: frozenset[str] = frozenset(
    {
        "llama3.1",
        "llama3.1:8b",
        "llama3.1:70b",
        "llama3.2:3b",
        "hermes3",
        "hermes3:8b",
        "mistral-nemo",
        "mistral",
        "qwen2.5",
        "qwen2.5:7b",
        "qwen2.5:14b",
        "qwen2.5:72b",
        "qwen2.5-coder",
        "firefunction-v2",
        "command-r-plus",
    }
)


def _model_supports_tools(model_name: str) -> bool:
    """Heuristic check whether a given Ollama model supports native tool calling."""
    name_lower = model_name.lower().strip()
    # 1B and 0.5B models lack parameter capacity for function calling and get confused by tool schemas
    if ":1b" in name_lower or ":0.5b" in name_lower or name_lower.endswith("1b") or "1b" in name_lower.split(":"):
        return False
    if name_lower in _TOOL_CAPABLE_MODELS:
        return True
    base_name = name_lower.split(":")[0]
    return base_name in {
        m.split(":")[0] for m in _TOOL_CAPABLE_MODELS if not (":1b" in m or ":0.5b" in m)
    }


def _tools_to_system_prompt(tools: list[dict[str, Any]]) -> str:
    """Embed tool schemas as JSON in a system message for models without native tool calling."""
    import json

    tool_descriptions = []
    for tool in tools:
        tool_descriptions.append(
            {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {}),
            }
        )
    return (
        "You have access to the following tools. To use a tool, respond with a JSON "
        "object on a single line in the format: "
        '{"tool": "<tool_name>", "arguments": {<args>}}\n\n'
        f"Available tools:\n{json.dumps(tool_descriptions, indent=2)}"
    )


def _convert_tools_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert generic tool schemas → OpenAI-compatible format for Ollama."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("parameters", {"type": "object", "properties": {}}),
            },
        }
        for t in tools
    ]


class OllamaProvider(AIProvider):
    """Ollama local LLM provider (OpenAI-compatible /v1 API).

    Ollama does not support tool calling on all models. When the configured model
    does not support tool calling natively, tool schemas are injected into the
    system prompt as a plain-text description, enabling soft tool use without
    structured output guarantees. Callers should handle both cases.
    """

    _DEFAULT_BASE_URL = "http://localhost:11434"
    _DEFAULT_MODEL = "llama3.2"

    def __init__(self) -> None:
        self._base_url = os.environ.get("OLLAMA_BASE_URL", self._DEFAULT_BASE_URL).rstrip("/")
        self._default_model = os.environ.get("OLLAMA_MODEL", self._DEFAULT_MODEL)

        # Reuse the async OpenAI client pointed at Ollama's /v1 endpoint.
        # Ollama does not require an API key but the openai SDK insists on one.
        self._client = openai.AsyncOpenAI(
            api_key="ollama",  # dummy key – Ollama ignores it
            base_url=f"{self._base_url}/v1",
            timeout=30.0,
        )

        self._native_tools = _model_supports_tools(self._default_model)
        logger.info(
            "OllamaProvider initialised | base_url=%s model=%s native_tools=%s",
            self._base_url,
            self._default_model,
            self._native_tools,
        )

    # ------------------------------------------------------------------ #
    #  Base-class contract                                                  #
    # ------------------------------------------------------------------ #

    @property
    def name(self) -> str:
        return "ollama"

    def supports_tools(self) -> bool:
        """Returns True only if the configured default model supports native tool calling."""
        return self._native_tools

    def supports_streaming(self) -> bool:
        return True

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _prepare_request(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]] | None]:
        """Prepare messages and tools for the API call.

        When the model does not support native tool calling, tools are omitted
        to prevent tool schema leakage into conversational responses.
        """
        native = _model_supports_tools(model)
        converted_messages: list[dict[str, Any]] = []

        # Carry existing system message content
        system_content: str | None = None
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                system_content = msg.get("content", "")
            else:
                converted_messages.append({"role": role, "content": msg.get("content", "")})

        if system_content:
            converted_messages.insert(0, {"role": "system", "content": system_content})

        return converted_messages, _convert_tools_openai(tools) if (tools and native) else None

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
        """Stream a chat completion from Ollama."""
        resolved_model = model or self._default_model
        converted_messages, openai_tools = self._prepare_request(messages, tools, resolved_model)

        # Cap tokens for responsive CPU inference (180 for 1B/small or explicit max_tokens)
        effective_max_tokens = max_tokens or (180 if not _model_supports_tools(resolved_model) else 512)
        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": converted_messages,
            "max_tokens": effective_max_tokens,
            "stream": True,
        }
        if openai_tools:
            kwargs["tools"] = openai_tools

        t0 = time.monotonic()

        try:
            stream = await self._client.chat.completions.create(**kwargs)
            buffer = ""
            filtering_schema_leak = True
            async for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        text = delta.content
                        if filtering_schema_leak:
                            buffer += text
                            stripped = buffer.lstrip()
                            if (
                                stripped.startswith("}{")
                                or stripped.startswith('{"type":"function')
                                or stripped.startswith('{"function"')
                            ):
                                if "}\n" in buffer:
                                    parts = buffer.split("}\n", 1)
                                    buffer = ""
                                    filtering_schema_leak = False
                                    remaining = parts[1].lstrip()
                                    if remaining:
                                        yield remaining
                                elif len(buffer) > 2048:
                                    buffer = ""
                                    filtering_schema_leak = False
                                continue
                            else:
                                filtering_schema_leak = False
                                yield buffer
                                buffer = ""
                        else:
                            yield text
            if buffer and not filtering_schema_leak:
                yield buffer
        except openai.APIConnectionError as exc:
            logger.error(
                "Cannot connect to Ollama at %s. Is Ollama running? Error: %s",
                self._base_url,
                exc,
            )
            raise
        except Exception as exc:
            logger.exception("Ollama streaming error after %.0fms", (time.monotonic() - t0) * 1000)
            raise

    # ------------------------------------------------------------------ #
    #  Non-streaming chat                                                  #
    # ------------------------------------------------------------------ #

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Non-streaming chat completion from Ollama."""
        resolved_model = model or self._default_model
        converted_messages, openai_tools = self._prepare_request(messages, tools, resolved_model)

        effective_max_tokens = max_tokens or (180 if not _model_supports_tools(resolved_model) else 512)
        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": converted_messages,
            "max_tokens": effective_max_tokens,
        }
        if openai_tools:
            kwargs["tools"] = openai_tools

        try:
            response = await self._client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            stripped = content.lstrip()
            if stripped.startswith("}{") or stripped.startswith('{"type":"function'):
                idx = content.rfind("}\n")
                if idx != -1:
                    content = content[idx + 2:].strip()
            return content
        except openai.APIConnectionError as exc:
            logger.error(
                "Cannot connect to Ollama at %s. Is Ollama running? Error: %s",
                self._base_url,
                exc,
            )
            raise
        except Exception as exc:
            logger.exception("Ollama chat error")
            raise

    # ------------------------------------------------------------------ #
    #  Embeddings                                                          #
    # ------------------------------------------------------------------ #

    async def embed(self, text: str) -> list[float]:
        """Generate embeddings via Ollama's /api/embeddings endpoint.

        Uses httpx directly because the OpenAI-compatible /v1/embeddings endpoint
        may not be available on all Ollama versions.
        """
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base_url}/api/embeddings",
                json={"model": self._default_model, "prompt": text},
            )
            resp.raise_for_status()
            data = resp.json()
            embedding = data.get("embedding", [])
            if not embedding:
                raise ValueError(f"Ollama returned empty embedding for model {self._default_model!r}")
            return embedding
