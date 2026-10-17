"""
memory/router.py – FastAPI routes for managing persistent memory entries.
"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.database.connection import get_db
from backend.database.models import User, MemoryEntryType
from backend.memory.service import memory_service

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    entry_type: MemoryEntryType = MemoryEntryType.fact
    tags: list[str] = Field(default_factory=list)
    source_conversation_id: str | None = None


class MemoryUpdateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    tags: list[str] | None = None


class MemoryResponse(BaseModel):
    id: str
    entry_type: str
    content: str
    tags: list[str]
    created_at: str
    source_conversation_id: str | None


@router.get("", response_model=list[MemoryResponse])
async def list_memories(
    entry_type: MemoryEntryType | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all persistent memories for the authenticated user."""
    memories = await memory_service.list_memories(db, current_user.id, entry_type=entry_type)
    return [
        MemoryResponse(
            id=m.id,
            entry_type=m.entry_type.value,
            content=m.content,
            tags=m.tags or [],
            created_at=m.created_at.isoformat(),
            source_conversation_id=m.source_conversation_id,
        )
        for m in memories
    ]


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    req: MemoryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually add a memory or approved fact."""
    m = await memory_service.add_memory(
        db,
        user_id=current_user.id,
        content=req.content,
        entry_type=req.entry_type,
        tags=req.tags,
        source_conversation_id=req.source_conversation_id,
    )
    return MemoryResponse(
        id=m.id,
        entry_type=m.entry_type.value,
        content=m.content,
        tags=m.tags or [],
        created_at=m.created_at.isoformat(),
        source_conversation_id=m.source_conversation_id,
    )


@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    req: MemoryUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a specific memory entry."""
    m = await memory_service.update_memory(
        db,
        user_id=current_user.id,
        memory_id=memory_id,
        content=req.content,
        tags=req.tags,
    )
    if not m:
        raise HTTPException(status_code=404, detail="Memory entry not found.")
    return MemoryResponse(
        id=m.id,
        entry_type=m.entry_type.value,
        content=m.content,
        tags=m.tags or [],
        created_at=m.created_at.isoformat(),
        source_conversation_id=m.source_conversation_id,
    )


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a memory entry."""
    success = await memory_service.delete_memory(db, current_user.id, memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory entry not found.")
    return None
