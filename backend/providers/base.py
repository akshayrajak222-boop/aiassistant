"""
Abstract base class for AI providers.

All AI provider implementations (Anthropic, OpenAI, Ollama, etc.) must subclass
AIProvider and implement all abstract methods. This ensures a consistent interface
across providers so the rest of the application remains provider-agnostic.
"""

from __future__ import annotations

import abc
import logging
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


class AIProvider(abc.ABC):
    """Abstract base class for all AI provider implementations.

    Subclasses must implement:
        - chat_stream: Streaming chat completion
        - chat: Non-streaming chat completion
        - embed: Text embeddings
        - supports_tools: Whether this provider supports tool/function calling
        - supports_streaming: Whether this provider supports SSE streaming
        - name: Provider identifier string
    """

    # ------------------------------------------------------------------ #
    #  Properties                                                           #
    # ------------------------------------------------------------------ #

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique provider identifier (e.g. 'anthropic', 'openai', 'ollama')."""

    # ------------------------------------------------------------------ #
    #  Capability checks                                                   #
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    def supports_tools(self) -> bool:
        """Return True if this provider supports tool/function calling."""

    @abc.abstractmethod
    def supports_streaming(self) -> bool:
        """Return True if this provider supports SSE streaming."""

    # ------------------------------------------------------------------ #
    #  Core API methods                                                    #
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream a chat completion, yielding text chunks as they arrive.

        Args:
            messages: List of conversation messages in provider-agnostic format:
                      [{"role": "user"|"assistant"|"system", "content": str}, ...]
            tools:    Optional list of tool schemas in provider-agnostic format.
                      The provider is responsible for converting to its native format.
            model:    Optional model override. Falls back to the provider's configured
                      default when None.

        Yields:
            str: Raw text chunks of the assistant response as they stream in.

        Raises:
            ProviderError: On any provider-level error (rate limit, auth, etc.)
        """
        # Subclasses must implement. This yield makes the type-checker happy.
        yield  # type: ignore[misc]

    @abc.abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> str:
        """Non-streaming chat completion; returns the full response text.

        Args:
            messages: List of conversation messages (same format as chat_stream).
            tools:    Optional list of tool schemas.
            model:    Optional model override.

        Returns:
            str: The complete assistant response text.

        Raises:
            ProviderError: On any provider-level error.
        """

    @abc.abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text.

        Args:
            text: The text to embed.

        Returns:
            list[float]: The embedding vector.

        Raises:
            ProviderError: On any provider-level error.
        """

    # ------------------------------------------------------------------ #
    #  Helper / convenience                                                #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} provider={self.name!r}>"
