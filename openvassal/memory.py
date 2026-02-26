"""Memory manager — conversation sessions + persistent user facts.

Provides two capabilities:
1. Conversation sessions via the SDK's SQLiteSession for per-chat history.
2. User facts that persist across all conversations (name, preferences, etc.).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.memory.sqlite_session import SQLiteSession

from openvassal.config import settings

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages conversation sessions and persistent user memory.

    All data is stored in the same SQLite database used by the DataStore,
    keeping everything in one place.
    """

    CONVERSATIONS_TABLE = "conversations"
    FACTS_TABLE = "user_facts"

    def __init__(self, db_path: Path | None = None):
        self._db_path = db_path or settings.db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()
        self._sessions: dict[str, SQLiteSession] = {}

    # ── Schema ────────────────────────────────────────────
    def _ensure_schema(self) -> None:
        """Create tables if they don't exist."""
        self._conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.CONVERSATIONS_TABLE} (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL DEFAULT 'New Chat',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.FACTS_TABLE} (
                id                  TEXT PRIMARY KEY,
                fact                TEXT NOT NULL,
                source_conversation TEXT,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    # ── Conversations ─────────────────────────────────────
    def create_conversation(self, title: str = "New Chat") -> dict[str, str]:
        """Create a new conversation, return its metadata."""
        conv_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            f"INSERT INTO {self.CONVERSATIONS_TABLE} (id, title, created_at, updated_at) "
            f"VALUES (?, ?, ?, ?)",
            (conv_id, title, now, now),
        )
        self._conn.commit()
        logger.info("Created conversation '%s' (title=%s)", conv_id, title)
        return {"id": conv_id, "title": title, "created_at": now, "updated_at": now}

    def list_conversations(self) -> list[dict[str, str]]:
        """List all conversations, newest first."""
        rows = self._conn.execute(
            f"SELECT id, title, created_at, updated_at FROM {self.CONVERSATIONS_TABLE} "
            f"ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]

    def get_conversation(self, conv_id: str) -> dict[str, str] | None:
        """Get a single conversation's metadata."""
        row = self._conn.execute(
            f"SELECT id, title, created_at, updated_at FROM {self.CONVERSATIONS_TABLE} "
            f"WHERE id = ?",
            (conv_id,),
        ).fetchone()
        return dict(row) if row else None

    def update_conversation_title(self, conv_id: str, title: str) -> None:
        """Update a conversation's title."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            f"UPDATE {self.CONVERSATIONS_TABLE} SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, conv_id),
        )
        self._conn.commit()

    def touch_conversation(self, conv_id: str) -> None:
        """Update the conversation's updated_at timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            f"UPDATE {self.CONVERSATIONS_TABLE} SET updated_at = ? WHERE id = ?",
            (now, conv_id),
        )
        self._conn.commit()

    def delete_conversation(self, conv_id: str) -> bool:
        """Delete a conversation and its session data."""
        # Remove session cache
        if conv_id in self._sessions:
            del self._sessions[conv_id]

        # Remove session messages (SDK table)
        try:
            self._conn.execute(
                "DELETE FROM agent_messages WHERE session_id = ?", (conv_id,)
            )
        except sqlite3.OperationalError:
            pass  # Table may not exist yet

        # Remove conversation metadata
        cursor = self._conn.execute(
            f"DELETE FROM {self.CONVERSATIONS_TABLE} WHERE id = ?", (conv_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    # ── Sessions ──────────────────────────────────────────
    def get_or_create_session(self, conv_id: str) -> SQLiteSession:
        """Get (or create) an SQLiteSession for a conversation."""
        if conv_id not in self._sessions:
            self._sessions[conv_id] = SQLiteSession(
                session_id=conv_id,
                db_path=str(self._db_path),
            )
        return self._sessions[conv_id]

    # ── User Facts ────────────────────────────────────────
    def get_all_facts(self) -> list[dict[str, str]]:
        """Return all user facts."""
        rows = self._conn.execute(
            f"SELECT id, fact, source_conversation, created_at, updated_at "
            f"FROM {self.FACTS_TABLE} ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]

    def get_facts_text(self) -> str:
        """Return all facts as a formatted string for injection into prompts."""
        facts = self.get_all_facts()
        if not facts:
            return "(No facts learned yet — pay attention to what the user shares!)"
        return "\n".join(f"- {f['fact']}" for f in facts)

    def add_fact(self, fact: str, source_conversation: str | None = None) -> str:
        """Add a user fact. Returns the fact ID."""
        fact_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            f"INSERT INTO {self.FACTS_TABLE} "
            f"(id, fact, source_conversation, created_at, updated_at) "
            f"VALUES (?, ?, ?, ?, ?)",
            (fact_id, fact, source_conversation, now, now),
        )
        self._conn.commit()
        logger.info("Saved user fact: %s", fact)
        return fact_id

    def delete_fact(self, fact_id: str) -> bool:
        """Delete a fact by ID."""
        cursor = self._conn.execute(
            f"DELETE FROM {self.FACTS_TABLE} WHERE id = ?", (fact_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def save_facts_from_list(
        self, facts: list[str], source_conversation: str | None = None
    ) -> int:
        """Save a list of fact strings (deduplicating against existing facts).

        Returns the number of new facts added.
        """
        existing = {f["fact"].lower().strip() for f in self.get_all_facts()}
        added = 0
        for fact in facts:
            fact = fact.strip()
            if fact and fact.lower() not in existing:
                self.add_fact(fact, source_conversation)
                existing.add(fact.lower())
                added += 1
        return added

    async def extract_and_save_facts(
        self,
        user_message: str,
        assistant_response: str,
        session_id: str | None = None,
    ) -> int:
        """Extract user facts from a conversation exchange and save them.

        Uses a lightweight LLM call to identify personal facts. Returns
        the number of new facts saved.
        """
        from agents import Agent, Runner

        extractor = Agent(
            name="FactExtractor",
            instructions=(
                "You are a fact extractor. Given a conversation exchange between a user "
                "and an AI assistant, extract any personal facts about the USER. "
                "Personal facts include: name, location, job, company, preferences, "
                "habits, family, hobbies, technical skills, timezone, etc.\n\n"
                "Rules:\n"
                "- Only extract facts about the USER, not the assistant.\n"
                "- Only extract facts that are clearly stated or strongly implied.\n"
                "- Do NOT include conversational context or questions.\n"
                "- Output ONLY a JSON array of fact strings. Example:\n"
                '  ["User\'s name is James", "User works on OpenSearch"]\n'
                "- If no personal facts are found, output: []\n"
                "- Keep facts concise (one sentence each).\n"
                "- Do not repeat facts that are essentially the same.\n"
            ),
            model=settings.resolve_model(settings.default_model),
        )

        prompt = (
            f"USER MESSAGE:\n{user_message}\n\n"
            f"ASSISTANT RESPONSE:\n{assistant_response}"
        )

        try:
            result = await Runner.run(extractor, input=prompt)
            raw = result.final_output.strip()
            # Parse the JSON array from the response
            # Handle cases where the model wraps it in markdown code blocks
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            facts = json.loads(raw)
            if isinstance(facts, list) and facts:
                count = self.save_facts_from_list(facts, session_id)
                logger.info(
                    "Extracted %d facts (%d new) from conversation",
                    len(facts),
                    count,
                )
                return count
        except Exception:
            logger.debug("Fact extraction failed (non-critical)", exc_info=True)
        return 0
