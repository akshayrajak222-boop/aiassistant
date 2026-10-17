"""
auth/utils.py – JWT signing/verification and password hashing helpers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.config import get_settings

logger = structlog.get_logger(__name__)

import bcrypt

# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*."""
    # Ensure plain is bytes and truncated to 72 bytes max for bcrypt
    pwd_bytes = plain.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*."""
    try:
        pwd_bytes = plain.encode("utf-8")[:72]
        hashed_bytes = hashed.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception:
        return False


# ── JWT helpers ───────────────────────────────────────────────────────────────

def _signing_key() -> str:
    """Return the appropriate signing key for the configured algorithm."""
    settings = get_settings()
    if settings.jwt_algorithm == "RS256":
        if not settings.jwt_private_key:
            raise ValueError("JWT_PRIVATE_KEY is required for RS256")
        return settings.jwt_private_key
    return settings.jwt_secret_key


def _verification_key() -> str:
    """Return the appropriate verification key for the configured algorithm."""
    settings = get_settings()
    if settings.jwt_algorithm == "RS256":
        if not settings.jwt_public_key:
            raise ValueError("JWT_PUBLIC_KEY is required for RS256")
        return settings.jwt_public_key
    return settings.jwt_secret_key


def create_access_token(
    subject: str,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token."""
    settings = get_settings()
    now = datetime.now(tz=timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))

    claims: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    if extra_claims:
        claims.update(extra_claims)

    return jwt.encode(claims, _signing_key(), algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    """Create a signed JWT refresh token with a longer TTL."""
    settings = get_settings()
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(days=settings.refresh_token_expire_days)

    claims: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(claims, _signing_key(), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT. Returns the payload or None on failure."""
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            _verification_key(),
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != "access":
            logger.warning("auth.wrong_token_type", token_type=payload.get("type"))
            return None
        return payload
    except JWTError as exc:
        logger.debug("auth.jwt_decode_failed", error=str(exc))
        return None


def decode_refresh_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT refresh token."""
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            _verification_key(),
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError as exc:
        logger.debug("auth.refresh_decode_failed", error=str(exc))
        return None
