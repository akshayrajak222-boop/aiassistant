"""
agent/router.py – FastAPI routes for conversations, SSE streaming, and message management.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, AsyncIterator
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agent.hermes_integration import agent_service
from backend.auth.dependencies import get_current_user
from backend.database.connection import get_db
from backend.database.models import (
    Conversation,
    Message,
    MessageRole,
    User,
    UserSettings,
)
from backend.memory.service import memory_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["agent"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class ConversationCreateRequest(BaseModel):
    title: str = Field(default="New Conversation", max_length=255)


class ConversationUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class MessageSendRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(..., min_length=1, max_length=10000)
    model: str | None = None


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    tool_calls: dict[str, Any] | None
    created_at: str


class ConversationDetailResponse(BaseModel):
    id: str
    title: str
    created_at: str
    is_archived: bool
    messages: list[MessageResponse]


class ConversationSummaryResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    is_archived: bool


# ── Conversation CRUD ────────────────────────────────────────────────────────

@router.get("/conversations", response_model=list[ConversationSummaryResponse])
async def list_conversations(
    include_archived: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all conversations for the authenticated user."""
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(desc(Conversation.updated_at))
    )
    if not include_archived:
        stmt = stmt.where(Conversation.is_archived == False)

    res = await db.execute(stmt)
    convs = res.scalars().all()
    return [
        ConversationSummaryResponse(
            id=c.id,
            title=c.title,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
            is_archived=c.is_archived,
        )
        for c in convs
    ]


@router.post("/conversations", response_model=ConversationSummaryResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    req: ConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new conversation session."""
    conv = Conversation(
        user_id=current_user.id,
        title=req.title,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationSummaryResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
        is_archived=conv.is_archived,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get conversation details and full message history."""
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    )
    res = await db.execute(stmt)
    conv = res.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    stmt_msgs = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    res_msgs = await db.execute(stmt_msgs)
    msgs = res_msgs.scalars().all()

    return ConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        is_archived=conv.is_archived,
        messages=[
            MessageResponse(
                id=m.id,
                role=m.role.value,
                content=m.content,
                tool_calls=m.tool_calls,
                created_at=m.created_at.isoformat(),
            )
            for m in msgs
        ],
    )


@router.put("/conversations/{conversation_id}/title", response_model=ConversationSummaryResponse)
async def update_conversation_title(
    conversation_id: str,
    req: ConversationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update title of a conversation."""
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    )
    res = await db.execute(stmt)
    conv = res.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    conv.title = req.title.strip()
    await db.commit()
    await db.refresh(conv)
    return ConversationSummaryResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
        is_archived=conv.is_archived,
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Archive a conversation."""
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    )
    res = await db.execute(stmt)
    conv = res.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    conv.is_archived = True
    await db.commit()
    return None


# ── Streaming Chat Endpoint ──────────────────────────────────────────────────

@router.post("/chat/stream")
async def chat_stream(
    req: MessageSendRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream AI response tokens and tool events via Server-Sent Events (SSE)."""
    # 1. Resolve or create conversation
    conv_id = req.conversation_id
    if not conv_id:
        new_title = req.message[:40] + ("..." if len(req.message) > 40 else "")
        conv = Conversation(user_id=current_user.id, title=new_title)
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        conv_id = conv.id
    else:
        stmt = select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == current_user.id,
        )
        res = await db.execute(stmt)
        conv = res.scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found.")

    # 2. Persist user message
    user_msg = Message(
        conversation_id=conv_id,
        role=MessageRole.user,
        content=req.message,
    )
    db.add(user_msg)
    await db.commit()

    # 3. Fetch past messages for context
    stmt_history = (
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at)
    )
    hist_res = await db.execute(stmt_history)
    history_records = hist_res.scalars().all()
    history = [
        {"role": m.role.value, "content": m.content}
        for m in history_records[:-1]  # Exclude current message since we pass user_message
    ]

    # 4. Fetch user preferences & persistent memory context
    stmt_settings = select(UserSettings).where(UserSettings.user_id == current_user.id)
    settings_res = await db.execute(stmt_settings)
    settings = settings_res.scalar_one_or_none()

    assistant_name = settings.assistant_name if settings else "Jarvis"
    base_instructions = settings.system_instructions if settings and settings.system_instructions else (
        f"You are {assistant_name}, a highly intelligent, proactive, and concise personal AI assistant. "
        "Help the user accomplish their tasks efficiently."
    )

    recent_texts = [m.content for m in history_records[-5:]]
    memory_context = await memory_service.get_relevant_context(db, current_user.id, recent_texts)

    full_system_prompt = f"{base_instructions}\n\n{memory_context}"

    task_id = str(uuid.uuid4())
    user_id = current_user.id

    async def event_generator() -> AsyncIterator[str]:
        assistant_content = []
        tool_calls_record = []

        # Emit initial conversation_id event
        yield f"event: conversation_id\ndata: {json.dumps({'conversation_id': conv_id})}\n\n"

        try:
            async for event in agent_service.run_task(
                user_message=req.message,
                conversation_history=history,
                system_prompt=full_system_prompt,
                user_id=user_id,
                task_id=task_id,
                model_override=req.model,
                context={"timezone": settings.timezone if settings else "UTC"},
            ):
                if event.type == "text":
                    assistant_content.append(event.content)
                elif event.type in ("tool_call", "tool_result"):
                    tool_calls_record.append(event.to_json())

                # SSE chunk
                yield f"event: {event.type}\ndata: {event.to_json()}\n\n"

            # 5. Persist assistant response to DB
            full_text = "".join(assistant_content)
            if full_text:
                assistant_msg = Message(
                    conversation_id=conv_id,
                    role=MessageRole.assistant,
                    content=full_text,
                    tool_calls={"events": tool_calls_record} if tool_calls_record else None,
                )
                db.add(assistant_msg)
                await db.commit()

        except Exception as exc:
            logger.exception("Error in SSE event_generator")
            err_data = json.dumps({"error": str(exc)})
            yield f"event: error\ndata: {err_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
