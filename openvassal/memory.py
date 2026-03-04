"""Memory manager — unified cross-agent memory via mem0.

Provides two capabilities:
1. Semantic memory via mem0 — auto-extraction, search, and injection of
   personal knowledge across agents and sessions.
2. Conversation metadata — SQLite-backed conversation list (title, timestamps).
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openvassal.config import settings

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages cross-agent memory via mem0 and conversation metadata via SQLite.

    mem0 handles the heavy lifting: extracting facts from conversations,
    semantic search, deduplication, and forgetting. We just provide a
    thin wrapper that plugs into the rest of OpenVassal.
    """

    CONVERSATIONS_TABLE = "conversations"

    def __init__(self, db_path: Path | None = None, user_id: str | None = None):
        self._db_path = db_path or settings.db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

        self._user_id = user_id or settings.mem0_user_id
        self._mem0 = None  # lazy init

    # ── mem0 client (lazy) ────────────────────────────────
    def _get_mem0(self):
        """Lazily initialize the mem0 Memory client."""
        if self._mem0 is None:
            try:
                from mem0 import Memory

                config = {
                    "version": "v1.1",
                }
                self._mem0 = Memory.from_config(config)
                logger.info("mem0 Memory initialized (local mode)")
            except Exception:
                logger.warning("mem0 initialization failed — memory features disabled", exc_info=True)
        return self._mem0

    # ── Schema (conversations only) ───────────────────────
    def _ensure_schema(self) -> None:
        self._conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.CONVERSATIONS_TABLE} (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL DEFAULT 'New Chat',
                agent_name  TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    # ── Conversations ─────────────────────────────────────
    def create_conversation(self, title: str = "New Chat", agent_name: str = "") -> dict[str, str]:
        conv_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            f"INSERT INTO {self.CONVERSATIONS_TABLE} "
            f"(id, title, agent_name, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (conv_id, title, agent_name, now, now),
        )
        self._conn.commit()
        logger.info("Created conversation '%s' (title=%s)", conv_id, title)
        return {"id": conv_id, "title": title, "agent_name": agent_name,
                "created_at": now, "updated_at": now}

    def list_conversations(self) -> list[dict[str, str]]:
        rows = self._conn.execute(
            f"SELECT id, title, agent_name, created_at, updated_at "
            f"FROM {self.CONVERSATIONS_TABLE} ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]

    def get_conversation(self, conv_id: str) -> dict[str, str] | None:
        row = self._conn.execute(
            f"SELECT id, title, agent_name, created_at, updated_at "
            f"FROM {self.CONVERSATIONS_TABLE} WHERE id = ?",
            (conv_id,),
        ).fetchone()
        return dict(row) if row else None

    def update_conversation_title(self, conv_id: str, title: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            f"UPDATE {self.CONVERSATIONS_TABLE} SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, conv_id),
        )
        self._conn.commit()

    def touch_conversation(self, conv_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            f"UPDATE {self.CONVERSATIONS_TABLE} SET updated_at = ? WHERE id = ?",
            (now, conv_id),
        )
        self._conn.commit()

    def delete_conversation(self, conv_id: str) -> bool:
        cursor = self._conn.execute(
            f"DELETE FROM {self.CONVERSATIONS_TABLE} WHERE id = ?", (conv_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    # ── mem0 Memory Operations ────────────────────────────
    def add_memory(
        self,
        text: str,
        agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict | None:
        """Add a memory entry via mem0."""
        mem0 = self._get_mem0()
        if mem0 is None:
            return None
        try:
            result = mem0.add(
                text,
                user_id=self._user_id,
                agent_id=agent_id,
                metadata=metadata or {},
            )
            logger.info("mem0 add: %s", result)
            return result
        except Exception:
            logger.debug("mem0 add failed", exc_info=True)
            return None

    def search_memory(self, query: str, limit: int = 10) -> list[dict]:
        """Search memories semantically via mem0."""
        mem0 = self._get_mem0()
        if mem0 is None:
            return []
        try:
            results = mem0.search(query, user_id=self._user_id, limit=limit)
            # mem0 returns {"results": [...]} or a list directly
            if isinstance(results, dict):
                return results.get("results", [])
            return results
        except Exception:
            logger.debug("mem0 search failed", exc_info=True)
            return []

    def get_all_memories(self) -> list[dict]:
        """Get all memories for the current user via mem0."""
        mem0 = self._get_mem0()
        if mem0 is None:
            return []
        try:
            results = mem0.get_all(user_id=self._user_id)
            # mem0 returns {"results": [...]} or a list directly
            if isinstance(results, dict):
                return results.get("results", [])
            return results
        except Exception:
            logger.debug("mem0 get_all failed", exc_info=True)
            return []

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a specific memory by ID via mem0."""
        mem0 = self._get_mem0()
        if mem0 is None:
            return False
        try:
            mem0.delete(memory_id)
            return True
        except Exception:
            logger.debug("mem0 delete failed", exc_info=True)
            return False

    def get_memory_context(self, query: str = "", limit: int = 5) -> str:
        """Get relevant memories formatted for injection into agent context.

        If a query is provided, searches semantically. Otherwise returns
        recent memories.
        """
        if query:
            memories = self.search_memory(query, limit=limit)
        else:
            memories = self.get_all_memories()[:limit]

        if not memories:
            return "(No relevant memories found)"

        lines = []
        for mem in memories:
            text = mem.get("memory", mem.get("text", str(mem)))
            lines.append(f"- {text}")
        return "\n".join(lines)

    def save_interaction(
        self,
        user_message: str,
        assistant_response: str,
        agent_id: str | None = None,
    ) -> None:
        """Save a conversation exchange to mem0 for automatic fact extraction.

        mem0 will automatically extract and store relevant facts from the
        conversation, deduplicating against existing memories.
        """
        messages = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_response},
        ]
        mem0 = self._get_mem0()
        if mem0 is None:
            return
        try:
            mem0.add(
                messages,
                user_id=self._user_id,
                agent_id=agent_id,
            )
        except Exception:
            logger.debug("mem0 save_interaction failed (non-critical)", exc_info=True)
