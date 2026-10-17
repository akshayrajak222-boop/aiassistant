"""
ProviderFactory – reads AI_PROVIDER env var and returns the correct AIProvider.

Supported values for AI_PROVIDER:
    anthropic  (requires ANTHROPIC_API_KEY)
    openai     (requires OPENAI_API_KEY)
    ollama     (requires OLLAMA_BASE_URL or falls back to localhost)

The factory validates on startup that required credentials are present and
raises a clear ValueError if they are missing.
"""

from __future__ import annotations

import logging
import os

from backend.providers.base import AIProvider

logger = logging.getLogger(__name__)

_PROVIDER_MAP = {
    "anthropic": ("backend.providers.anthropic_provider", "AnthropicProvider"),
    "openai":    ("backend.providers.openai_provider",    "OpenAIProvider"),
    "ollama":    ("backend.providers.ollama_provider",    "OllamaProvider"),
}

# Credentials that MUST be set for each provider (checked on startup)
_REQUIRED_ENV: dict[str, list[str]] = {
    "anthropic": ["ANTHROPIC_API_KEY"],
    "openai":    ["OPENAI_API_KEY"],
    "ollama":    [],  # No hard credential requirement – just a reachable server
}


class ProviderFactory:
    """Factory that constructs and validates AI providers based on environment config."""

    _instance: AIProvider | None = None

    @classmethod
    def get_provider(cls) -> AIProvider:
        """Return a cached singleton provider instance.

        Reads ``AI_PROVIDER`` from the environment (default: ``openai``).
        Validates that all required credentials are present, then constructs
        and caches the provider.

        Raises:
            ValueError: If the provider name is unknown or required env vars
                        are missing.
        """
        if cls._instance is not None:
            return cls._instance

        provider_name = os.environ.get("AI_PROVIDER", "openai").strip().lower()

        if provider_name not in _PROVIDER_MAP:
            supported = ", ".join(sorted(_PROVIDER_MAP.keys()))
            raise ValueError(
                f"Unknown AI_PROVIDER={provider_name!r}. Supported: {supported}"
            )

        # Validate credentials
        missing = [
            var
            for var in _REQUIRED_ENV[provider_name]
            if not os.environ.get(var)
        ]
        if missing:
            raise ValueError(
                f"Provider {provider_name!r} requires the following environment "
                f"variables which are not set: {', '.join(missing)}"
            )

        module_path, class_name = _PROVIDER_MAP[provider_name]
        import importlib

        module = importlib.import_module(module_path)
        provider_cls = getattr(module, class_name)
        instance: AIProvider = provider_cls()

        logger.info("ProviderFactory: selected provider=%s", instance.name)
        cls._instance = instance
        return instance

    @classmethod
    def reset(cls) -> None:
        """Clear the cached provider instance (useful in tests)."""
        cls._instance = None

    @classmethod
    def create(cls, provider_name: str) -> AIProvider:
        """Create a provider by explicit name (does not affect the singleton cache).

        Args:
            provider_name: One of 'anthropic', 'openai', 'ollama'.

        Returns:
            AIProvider: A fresh provider instance.

        Raises:
            ValueError: If the name is unknown or credentials are missing.
        """
        provider_name = provider_name.strip().lower()

        if provider_name not in _PROVIDER_MAP:
            supported = ", ".join(sorted(_PROVIDER_MAP.keys()))
            raise ValueError(
                f"Unknown provider {provider_name!r}. Supported: {supported}"
            )

        missing = [
            var
            for var in _REQUIRED_ENV[provider_name]
            if not os.environ.get(var)
        ]
        if missing:
            raise ValueError(
                f"Provider {provider_name!r} requires: {', '.join(missing)}"
            )

        module_path, class_name = _PROVIDER_MAP[provider_name]
        import importlib

        module = importlib.import_module(module_path)
        provider_cls = getattr(module, class_name)
        return provider_cls()


def get_provider() -> AIProvider:
    """Convenience module-level function to get the configured AIProvider."""
    return ProviderFactory.get_provider()

