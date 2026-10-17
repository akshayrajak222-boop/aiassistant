"""
memory/service.py – Persistent memory service for user preferences, facts, and context.
"""

from __future__ import annotations

import logging
from typing import Any
from sqlalchemy import select, delete, update, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import MemoryEntry, MemoryEntryType

logger = logging.getLogger(__name__)


class MemoryService:
    """Service managing persistent memory entries across conversations."""

    async def add_memory(
        self,
        db: AsyncSession,
        user_id: str,
        content: str,
        entry_type: MemoryEntryType = MemoryEntryType.fact,
        tags: list[str] | None = None,
        source_conversation_id: str | None = None,
    ) -> MemoryEntry:
        """Create a new memory entry."""
        entry = MemoryEntry(
            user_id=user_id,
            content=content.strip(),
            entry_type=entry_type,
            tags=tags or [],
            source_conversation_id=source_conversation_id,
            is_active=True,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        logger.info(f"Added memory entry {entry.id} ({entry_type}) for user {user_id}")
        return entry

    async def list_memories(
        self,
        db: AsyncSession,
        user_id: str,
        entry_type: MemoryEntryType | None = None,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        """List active memory entries for a user."""
        stmt = (
            select(MemoryEntry)
            .where(MemoryEntry.user_id == user_id, MemoryEntry.is_active == True)
            .order_by(desc(MemoryEntry.created_at))
            .limit(limit)
        )
        if entry_type:
            stmt = stmt.where(MemoryEntry.entry_type == entry_type)

        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def search_memory(
        self,
        db: AsyncSession,
        user_id: str,
        query: str,
        limit: int = 5,
    ) -> list[MemoryEntry]:
        """Search memory entries using keyword / text matching."""
        tokens = [t.strip().lower() for t in query.split() if len(t.strip()) > 2]
        stmt = select(MemoryEntry).where(
            MemoryEntry.user_id == user_id,
            MemoryEntry.is_active == True,
        )
        res = await db.execute(stmt)
        entries = res.scalars().all()

        if not tokens:
            return list(entries[:limit])

        # Rank matches by keyword overlap
        scored: list[tuple[int, MemoryEntry]] = []
        for e in entries:
            score = 0
            text_lower = e.content.lower()
            tags_lower = [t.lower() for t in (e.tags or [])]
            for t in tokens:
                if t in text_lower:
                    score += 2
                if any(t in tag for tag in tags_lower):
                    score += 3
            if score > 0:
                scored.append((score, e))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:limit]]

    async def update_memory(
        self,
        db: AsyncSession,
        user_id: str,
        memory_id: str,
        content: str,
        tags: list[str] | None = None,
    ) -> MemoryEntry | None:
        """Update an existing memory entry."""
        stmt = select(MemoryEntry).where(
            MemoryEntry.id == memory_id,
            MemoryEntry.user_id == user_id,
        )
        res = await db.execute(stmt)
        entry = res.scalar_one_or_none()
        if not entry:
            return None

        entry.content = content.strip()
        if tags is not None:
            entry.tags = tags
        await db.commit()
        await db.refresh(entry)
        return entry

    async def delete_memory(
        self,
        db: AsyncSession,
        user_id: str,
        memory_id: str,
    ) -> bool:
        """Permanently or logically delete a memory entry."""
        stmt = select(MemoryEntry).where(
            MemoryEntry.id == memory_id,
            MemoryEntry.user_id == user_id,
        )
        res = await db.execute(stmt)
        entry = res.scalar_one_or_none()
        if not entry:
            return False

        await db.delete(entry)
        await db.commit()
        return True

    async def get_relevant_context(
        self,
        db: AsyncSession,
        user_id: str,
        recent_messages: list[str],
        limit: int = 6,
    ) -> str:
        """Assemble relevant persistent memory into a concise markdown context block for the agent."""
        query = " ".join(recent_messages[-3:]) if recent_messages else ""
        relevant = await self.search_memory(db, user_id, query, limit=limit)
        if not relevant:
            # Fall back to high-priority preferences
            prefs = await self.list_memories(db, user_id, entry_type=MemoryEntryType.preference, limit=3)
            relevant = prefs

        if not relevant:
            return ""

        lines = ["\n[PERSISTENT USER MEMORY & PREFERENCES]"]
        for entry in relevant:
            prefix = f"[{entry.entry_type.value.upper()}]"
            lines.append(f"- {prefix} {entry.content}")
        lines.append("[END PERSISTENT MEMORY]\n")
        return "\n".join(lines)


memory_service = MemoryService()
