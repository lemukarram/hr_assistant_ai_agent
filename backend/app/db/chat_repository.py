"""
Chat session and message persistence.

Provides:
  - ChatRepository class (used where a DB session is already in scope)
  - Module-level async functions (used by api/chat.py via `from app.db import chat_repository`)
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session


# ── Repository Class ──────────────────────────────────────────────────────────

class ChatRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create_session(self, employee_id: str, title: str | None = None) -> str:
        """Return UUID of the active session for an employee, creating one if needed."""
        result = await self.db.execute(
            text(
                """
                SELECT id
                FROM   chat_sessions
                WHERE  employee_id = :emp_id
                  AND  is_active   = TRUE
                ORDER  BY started_at DESC
                LIMIT  1
                """
            ),
            {"emp_id": str(employee_id)},
        )
        row = result.scalar()
        if row:
            return str(row)

        result = await self.db.execute(
            text(
                """
                INSERT INTO chat_sessions (employee_id, title, started_at, is_active)
                VALUES (:emp_id, :title, NOW(), TRUE)
                RETURNING id
                """
            ),
            {"emp_id": str(employee_id), "title": title},
        )
        await self.db.commit()
        return str(result.scalar())

    async def create_new_session(self, employee_id: str, title: str | None = None) -> str:
        """Deactivate all existing sessions and create a fresh one."""
        await self.db.execute(
            text(
                "UPDATE chat_sessions SET is_active = FALSE WHERE employee_id = :emp_id"
            ),
            {"emp_id": str(employee_id)},
        )
        result = await self.db.execute(
            text(
                """
                INSERT INTO chat_sessions (employee_id, title, started_at, is_active)
                VALUES (:emp_id, :title, NOW(), TRUE)
                RETURNING id
                """
            ),
            {"emp_id": str(employee_id), "title": title},
        )
        await self.db.commit()
        return str(result.scalar())

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        intent: str | None = None,
        tool_calls: list | None = None,
        sources: list | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Persist one chat message. Returns the new message UUID."""
        result = await self.db.execute(
            text(
                """
                INSERT INTO chat_messages
                    (session_id, role, content, intent, tool_calls, sources, metadata, created_at)
                VALUES
                    (:sid, :role, :content, :intent,
                     :tool_calls::jsonb, :sources::jsonb, :metadata::jsonb, NOW())
                RETURNING id
                """
            ),
            {
                "sid":        str(session_id),
                "role":       role,
                "content":    content,
                "intent":     intent,
                "tool_calls": json.dumps(tool_calls or [], ensure_ascii=False),
                "sources":    json.dumps(sources or [], ensure_ascii=False),
                "metadata":   json.dumps(metadata or {}, ensure_ascii=False),
            },
        )
        await self.db.commit()
        return str(result.scalar())

    async def get_history(
        self,
        session_id: str,
        employee_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Return ordered message history for a session.
        Enforces ownership: session must belong to employee_id.
        """
        result = await self.db.execute(
            text(
                """
                SELECT cm.role, cm.content, cm.intent, cm.sources, cm.created_at
                FROM   chat_messages cm
                JOIN   chat_sessions cs ON cs.id = cm.session_id
                WHERE  cm.session_id  = :sid
                  AND  cs.employee_id = :emp_id
                ORDER  BY cm.created_at ASC
                LIMIT  :limit
                """
            ),
            {
                "sid":    str(session_id),
                "emp_id": str(employee_id),
                "limit":  limit,
            },
        )
        return [dict(r) for r in result.mappings().all()]

    async def list_sessions(self, employee_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """List chat sessions for an employee, newest first."""
        result = await self.db.execute(
            text(
                """
                SELECT cs.id, cs.title, cs.started_at,
                       COUNT(cm.id) AS message_count
                FROM   chat_sessions cs
                LEFT JOIN chat_messages cm ON cm.session_id = cs.id
                WHERE  cs.employee_id = :emp_id
                GROUP  BY cs.id, cs.title, cs.started_at
                ORDER  BY cs.started_at DESC
                LIMIT  :limit
                """
            ),
            {"emp_id": str(employee_id), "limit": limit},
        )
        return [
            {**dict(r), "id": str(r["id"])}
            for r in result.mappings().all()
        ]


# ── Module-level helpers (used by api/chat.py as chat_repository.func()) ─────

async def get_session_history(
    session_id: str,
    employee_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return message history for a session. Creates session if it doesn't exist."""
    async with get_db_session() as db:
        repo = ChatRepository(db)
        # Ensure session exists and belongs to this employee
        await repo.get_or_create_session(employee_id)
        return await repo.get_history(session_id, employee_id, limit)


async def save_message(
    session_id: str,
    employee_id: str,
    user_message: str,
    assistant_message: str,
    intent: str | None = None,
    sources: list | None = None,
) -> None:
    """Persist a complete turn (user + assistant messages)."""
    async with get_db_session() as db:
        repo = ChatRepository(db)
        # Ensure session exists
        await repo.get_or_create_session(employee_id)
        await repo.save_message(
            session_id=session_id,
            role="user",
            content=user_message,
        )
        await repo.save_message(
            session_id=session_id,
            role="assistant",
            content=assistant_message,
            intent=intent,
            sources=sources,
        )


async def list_sessions(employee_id: str) -> list[dict[str, Any]]:
    """List chat sessions for an employee."""
    async with get_db_session() as db:
        repo = ChatRepository(db)
        return await repo.list_sessions(employee_id)


async def create_session(employee_id: str, title: str | None = None) -> str:
    """Create a new chat session, deactivating any previous one."""
    async with get_db_session() as db:
        repo = ChatRepository(db)
        return await repo.create_new_session(employee_id, title)
