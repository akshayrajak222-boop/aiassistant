"""
config.py – Centralised Pydantic-Settings configuration.

All values are loaded from environment variables (or a .env file).
Sensitive fields are *never* logged or serialised.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import (
    AnyHttpUrl,
    EmailStr,
    Field,
    PostgresDsn,
    RedisDsn,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = "Axy AI Platform"
    assistant_name: str = "Axy"
    app_version: str = "1.0.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(64))

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/agentdb",
        description="Database connection string (sqlite+aiosqlite or postgresql+asyncpg)",
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: RedisDsn = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    redis_max_connections: int = 50

    # ── JWT Auth ──────────────────────────────────────────────────────────────
    jwt_algorithm: Literal["HS256", "RS256"] = "HS256"
    jwt_secret_key: str = Field(
        default_factory=lambda: secrets.token_urlsafe(64),
        description="Secret for HS256 signing (ignored when RS256 is used)",
    )
    # RS256 — provide PEM-encoded key material via env vars
    jwt_private_key: str | None = None
    jwt_public_key: str | None = None
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: list[AnyHttpUrl] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = True

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_default: str = "200/minute"
    rate_limit_auth: str = "20/minute"

    # ── AI Providers ──────────────────────────────────────────────────────────
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")
    ai_model: str | None = None
    default_ai_provider: Literal["openai", "anthropic", "ollama"] = "openai"
    default_model_openai: str = "gpt-4o"
    default_model_anthropic: str = "claude-3-5-sonnet-20241022"
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:1b"

    # ── Google / Gmail ────────────────────────────────────────────────────────
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    # ── Encryption (Fernet) for stored credentials ────────────────────────────
    encryption_key: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Fernet encryption key for credential storage",
    )

    # ── Celery ────────────────────────────────────────────────────────────────
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    # ── First-run admin account (optional) ───────────────────────────────────
    initial_admin_email: str | None = None
    initial_admin_password: str | None = None

    # ─────────────────────────────────────────────────────────────────────────
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list) -> list:
        """Allow comma-separated string from env var."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def _validate_required_for_production(self) -> "Settings":
        """Fail fast in production if critical values are still at defaults."""
        if self.environment == "production":
            if self.jwt_algorithm == "RS256":
                if not self.jwt_private_key or not self.jwt_public_key:
                    raise ValueError(
                        "RS256 algorithm requires JWT_PRIVATE_KEY and JWT_PUBLIC_KEY"
                    )
            if not any([self.openai_api_key, self.anthropic_api_key, self.default_ai_provider == "ollama"]):
                raise ValueError(
                    "At least one AI provider API key or ollama must be set in production"
                )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def database_url_str(self) -> str:
        return str(self.database_url)

    @property
    def redis_url_str(self) -> str:
        return str(self.redis_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
