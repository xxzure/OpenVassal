"""Daily Work Agent — calendar, tasks, email triage, and productivity.

This is a v1 sub-agent that demonstrates the plugin pattern.
"""

from __future__ import annotations

import json
from datetime import datetime

from agents import Agent, function_tool

from subordinates.agents.base import BaseAgent
from subordinates.models import DataCategory, DataRecord


class DailyWorkAgent(BaseAgent):
    """Sub-agent specialized in daily work management."""

    name = "Daily Work Agent"
    description = "Calendar, tasks, email triage, and daily productivity"

    def build_agent(self) -> Agent:
        return Agent(
            name=self.name,
            instructions=(
                "You are a productivity assistant. Help the user with:\n"
                "- Managing tasks and to-do lists\n"
                "- Calendar planning and scheduling\n"
                "- Email triage and prioritization\n"
                "- Daily planning and time management\n"
                "- Meeting notes and follow-ups\n\n"
                "Be organized, concise, and proactive about suggesting "
                "improvements to the user's workflow."
            ),
            model=self.model,
            tools=self.get_tools(),
        )

    def get_tools(self) -> list:
        store = self.data_store

        @function_tool
        def add_task(title: str, priority: str = "medium", due_date: str = "") -> str:
            """Add a task to the to-do list. Priority: low, medium, high."""
            record = DataRecord(
                category=DataCategory.DAILY,
                source="daily_work_agent",
                title=title,
                content=f"Priority: {priority}",
                metadata={
                    "type": "task",
                    "priority": priority,
                    "due_date": due_date,
                    "status": "pending",
                },
            )
            saved = store.save(record)
            return f"✅ Task added: '{title}' (priority: {priority}, id: {saved.id})"

        @function_tool
        def list_tasks(status: str = "all") -> str:
            """List tasks. Status filter: all, pending, done."""
            results = store.query(category=DataCategory.DAILY, limit=50)
            tasks = [r for r in results if r.metadata.get("type") == "task"]
            if status != "all":
                tasks = [t for t in tasks if t.metadata.get("status") == status]
            if not tasks:
                return "No tasks found."
            lines = []
            for t in tasks:
                status_icon = "✅" if t.metadata.get("status") == "done" else "⬜"
                pri = t.metadata.get("priority", "medium")
                due = t.metadata.get("due_date", "")
                due_str = f" (due: {due})" if due else ""
                lines.append(f"{status_icon} [{pri}] {t.title}{due_str}  (id: {t.id})")
            return "\n".join(lines)

        @function_tool
        def complete_task(task_id: str) -> str:
            """Mark a task as completed by its ID."""
            record = store.get(task_id)
            if not record:
                return f"Task '{task_id}' not found."
            record.metadata["status"] = "done"
            store.save(record)
            return f"✅ Task '{record.title}' marked as done."

        @function_tool
        def add_note(title: str, content: str) -> str:
            """Save a quick note (meeting notes, ideas, reminders)."""
            record = DataRecord(
                category=DataCategory.DAILY,
                source="daily_work_agent",
                title=title,
                content=content,
                metadata={"type": "note"},
            )
            store.save(record)
            return f"📝 Note saved: '{title}'"

        @function_tool
        def search_notes(query: str) -> str:
            """Search through saved notes."""
            results = store.query(category=DataCategory.DAILY, search=query, limit=10)
            notes = [r for r in results if r.metadata.get("type") == "note"]
            if not notes:
                return "No notes found matching your query."
            return "\n\n".join(f"### {n.title}\n{n.content}" for n in notes)

        return [add_task, list_tasks, complete_task, add_note, search_notes]
