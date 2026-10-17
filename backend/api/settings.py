"""
api/settings.py – User settings and assistant personalization endpoints.
"""

from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.database.connection import get_db
from backend.database.models import User, UserSettings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])


class UserSettingsUpdate(BaseModel):
    assistant_name: str = Field(..., min_length=1, max_length=100)
    system_instructions: str | None = Field(default=None, max_length=5000)
    preferred_language: str = Field(default="en", max_length=10)
    response_style: str = Field(default="balanced", max_length=50)
    voice_id: str | None = Field(default=None, max_length=100)
    timezone: str = Field(default="UTC", max_length=64)
    default_model: str | None = Field(default=None, max_length=100)
    ai_provider: str = Field(default="anthropic", max_length=50)


class UserSettingsResponse(BaseModel):
    assistant_name: str
    system_instructions: str | None
    preferred_language: str
    response_style: str
    voice_id: str | None
    timezone: str
    default_model: str | None
    ai_provider: str


@router.get("", response_model=UserSettingsResponse)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve settings for the current user."""
    stmt = select(UserSettings).where(UserSettings.user_id == current_user.id)
    res = await db.execute(stmt)
    s = res.scalar_one_or_none()
    if not s:
        # Default settings if none created yet
        s = UserSettings(
            user_id=current_user.id,
            assistant_name="Jarvis",
            preferred_language="en",
            response_style="balanced",
            timezone="UTC",
            ai_provider="anthropic",
        )
        db.add(s)
        await db.commit()
        await db.refresh(s)

    return UserSettingsResponse(
        assistant_name=s.assistant_name,
        system_instructions=s.system_instructions,
        preferred_language=s.preferred_language,
        response_style=s.response_style,
        voice_id=s.voice_id,
        timezone=s.timezone,
        default_model=s.default_model,
        ai_provider=s.ai_provider,
    )


@router.put("", response_model=UserSettingsResponse)
async def update_settings(
    req: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update settings for the current user."""
    stmt = select(UserSettings).where(UserSettings.user_id == current_user.id)
    res = await db.execute(stmt)
    s = res.scalar_one_or_none()
    if not s:
        s = UserSettings(user_id=current_user.id)
        db.add(s)

    s.assistant_name = req.assistant_name.strip()
    s.system_instructions = req.system_instructions
    s.preferred_language = req.preferred_language
    s.response_style = req.response_style
    s.voice_id = req.voice_id
    s.timezone = req.timezone
    s.default_model = req.default_model
    s.ai_provider = req.ai_provider

    await db.commit()
    await db.refresh(s)

    return UserSettingsResponse(
        assistant_name=s.assistant_name,
        system_instructions=s.system_instructions,
        preferred_language=s.preferred_language,
        response_style=s.response_style,
        voice_id=s.voice_id,
        timezone=s.timezone,
        default_model=s.default_model,
        ai_provider=s.ai_provider,
    )
