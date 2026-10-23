"""
auth/router.py – Authentication endpoints.

POST /api/auth/login     → access token (JSON) + refresh token (httponly cookie)
POST /api/auth/logout    → clear cookies
POST /api/auth/refresh   → rotate access token using refresh token
GET  /api/auth/me        → current user info
"""

from __future__ import annotations

from datetime import timedelta

import structlog
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.config import get_settings
from backend.database.connection import get_db
from backend.database.models import AuditEvent, User

from .dependencies import CurrentUser
from .schemas import LoginRequest, RefreshRequest, TokenResponse, UserResponse
from .utils import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, token: str):
    settings = get_settings()
    is_secure = settings.environment != "development"
    response.set_cookie(
        key="refresh_token",
        value=token,
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path="/api/auth",
    )


def _set_access_cookie(response: Response, token: str):
    settings = get_settings()
    is_secure = settings.environment != "development"
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path="/",
    )


async def _write_audit(
    db: AsyncSession,
    *,
    user_id: str | None,
    event_type: str,
    ip_address: str | None,
    details: dict | None = None,
):
    event = AuditEvent(
        user_id=user_id,
        event_type=event_type,
        resource_type="auth",
        ip_address=ip_address,
        details=details or {},
    )
    db.add(event)
    # committed by get_db on exit


# ── POST /api/auth/login ──────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate with email + password.

    Returns a short-lived access token in the JSON body and a long-lived
    refresh token in an httponly cookie.
    """
    settings = get_settings()
    ip = request.client.host if request.client else None

    result = await db.execute(select(User).where(User.email == body.email))
    user: User | None = result.scalars().first()

    if user is None or not verify_password(body.password, user.hashed_password):
        logger.warning("auth.login_failed", email=body.email, ip=ip)
        await _write_audit(db, user_id=None, event_type="login_failed", ip_address=ip,
                           details={"email": body.email})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    _set_refresh_cookie(response, refresh_token)
    _set_access_cookie(response, access_token)

    logger.info("auth.login_success", user_id=user.id, ip=ip)
    await _write_audit(db, user_id=user.id, event_type="login_success", ip_address=ip)

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


# ── POST /api/auth/logout ─────────────────────────────────────────────────────

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def logout(
    response: Response,
    current_user: CurrentUser,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Clear auth cookies and record the logout event."""
    ip = request.client.host if request.client else None

    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/auth")

    logger.info("auth.logout", user_id=current_user.id)
    await _write_audit(db, user_id=current_user.id, event_type="logout", ip_address=ip)


# ── POST /api/auth/refresh ────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshRequest,
    response: Response,
    refresh_token_cookie: str | None = Cookie(default=None, alias="refresh_token"),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Rotate an access token using a refresh token.

    Accepts the token from the request body *or* the httponly cookie.
    """
    settings = get_settings()
    raw_token: str | None = body.refresh_token or refresh_token_cookie

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    payload = decode_refresh_token(raw_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id: str = payload["sub"]
    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalars().first()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    new_access = create_access_token(subject=user.id)
    new_refresh = create_refresh_token(subject=user.id)

    _set_refresh_cookie(response, new_refresh)
    _set_access_cookie(response, new_access)

    logger.info("auth.token_refreshed", user_id=user.id)

    return TokenResponse(
        access_token=new_access,
        expires_in=settings.access_token_expire_minutes * 60,
    )


# ── GET /api/auth/me ──────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser) -> UserResponse:
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)


# ── POST /api/auth/register ────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Register a new user account.
    If accounts already exist, allows registration of personal admin user.
    """
    settings = get_settings()
    ip = request.client.host if request.client else None

    # Check if user already exists
    result = await db.execute(select(User).where(User.email == body.email))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    # Create new user
    new_user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    access_token = create_access_token(subject=new_user.id)
    refresh_token = create_refresh_token(subject=new_user.id)

    _set_refresh_cookie(response, refresh_token)
    _set_access_cookie(response, access_token)

    logger.info("auth.register_success", user_id=new_user.id, ip=ip)
    await _write_audit(db, user_id=new_user.id, event_type="register_success", ip_address=ip)

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )

