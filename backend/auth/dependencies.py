"""
auth/dependencies.py – FastAPI dependencies for JWT authentication.

Validates the access token from the Authorization header (Bearer) or
the `access_token` httponly cookie.
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import Cookie, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.config import get_settings
from backend.database.connection import get_db
from backend.database.models import User

from .utils import decode_access_token

logger = structlog.get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer)] = None,
    access_token: Annotated[str | None, Cookie(alias="access_token")] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract and validate the JWT, then return the authenticated User.

    Token resolution order:
      1. Authorization: Bearer <token>
      2. access_token httponly cookie
    """
    token: str | None = None

    if credentials is not None:
        token = credentials.credentials
    elif access_token is not None:
        token = access_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalars().first()

    if user is None:
        logger.warning("auth.user_not_found", user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    return user


# Alias for convenience
CurrentUser = Annotated[User, Depends(get_current_user)]
