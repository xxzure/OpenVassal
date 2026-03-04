"""Agent tools — reusable tool functions for CrewAI agents.

CrewAI agents use @tool decorated functions. These are organized here
as tool factories that accept a DataStore and return tool functions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crewai.tools import tool

if TYPE_CHECKING:
    from openvassal.data.store import DataStore


def get_coding_tools(data_store: DataStore) -> list:
    """Return coding-related tools bound to the given DataStore."""
    from openvassal.models import DataCategory, DataRecord

    @tool("save_code_snippet")
    def save_code_snippet(title: str, language: str, code: str) -> str:
        """Save a code snippet to the personal knowledge base for later reference.

        Args:
            title: Brief description of the code snippet
            language: Programming language of the snippet
            code: The code content to save
        """
        record = DataRecord(
            category=DataCategory.DAILY,
            source="coding_agent",
            title=f"[{language}] {title}",
            content=code,
            metadata={"language": language, "type": "code_snippet"},
        )
        data_store.save(record)
        return f"Saved code snippet '{title}' ({language})"

    @tool("search_saved_code")
    def search_saved_code(query: str) -> str:
        """Search previously saved code snippets.

        Args:
            query: Search query to find matching code snippets
        """
        results = data_store.query(search=query, limit=5)
        if not results:
            return "No saved code snippets found matching your query."
        lines = []
        for r in results:
            lines.append(f"### {r.title}\n```\n{r.content[:500]}\n```\n")
        return "\n".join(lines)

    return [save_code_snippet, search_saved_code]


def get_daily_work_tools(data_store: DataStore) -> list:
    """Return daily work / productivity tools bound to the given DataStore."""
    from openvassal.models import DataCategory, DataRecord

    @tool("add_task")
    def add_task(title: str, priority: str = "medium", due_date: str = "") -> str:
        """Add a task to the to-do list.

        Args:
            title: Task description
            priority: Priority level — low, medium, or high
            due_date: Optional due date string
        """
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
        saved = data_store.save(record)
        return f"✅ Task added: '{title}' (priority: {priority}, id: {saved.id})"

    @tool("list_tasks")
    def list_tasks(status: str = "all") -> str:
        """List tasks. Status filter: all, pending, done.

        Args:
            status: Filter by status — all, pending, or done
        """
        results = data_store.query(category=DataCategory.DAILY, limit=50)
        tasks = [r for r in results if r.metadata.get("type") == "task"]
        if status != "all":
            tasks = [t for t in tasks if t.metadata.get("status") == status]
        if not tasks:
            return "No tasks found."
        lines = []
        for t in tasks:
            icon = "✅" if t.metadata.get("status") == "done" else "⬜"
            pri = t.metadata.get("priority", "medium")
            due = t.metadata.get("due_date", "")
            due_str = f" (due: {due})" if due else ""
            lines.append(f"{icon} [{pri}] {t.title}{due_str}  (id: {t.id})")
        return "\n".join(lines)

    @tool("complete_task")
    def complete_task(task_id: str) -> str:
        """Mark a task as completed by its ID.

        Args:
            task_id: The ID of the task to mark as done
        """
        record = data_store.get(task_id)
        if not record:
            return f"Task '{task_id}' not found."
        record.metadata["status"] = "done"
        data_store.save(record)
        return f"✅ Task '{record.title}' marked as done."

    @tool("add_note")
    def add_note(title: str, content: str) -> str:
        """Save a quick note (meeting notes, ideas, reminders).

        Args:
            title: Note title
            content: Note content
        """
        record = DataRecord(
            category=DataCategory.DAILY,
            source="daily_work_agent",
            title=title,
            content=content,
            metadata={"type": "note"},
        )
        data_store.save(record)
        return f"📝 Note saved: '{title}'"

    @tool("search_notes")
    def search_notes(query: str) -> str:
        """Search through saved notes.

        Args:
            query: Search query to find matching notes
        """
        results = data_store.query(category=DataCategory.DAILY, search=query, limit=10)
        notes = [r for r in results if r.metadata.get("type") == "note"]
        if not notes:
            return "No notes found matching your query."
        return "\n\n".join(f"### {n.title}\n{n.content}" for n in notes)

    return [add_task, list_tasks, complete_task, add_note, search_notes]


# ── Tool registry — maps tool names from agents.yaml to factories ──
TOOL_FACTORIES: dict[str, callable] = {
    "save_code_snippet": lambda ds: get_coding_tools(ds),
    "search_saved_code": lambda ds: get_coding_tools(ds),
    "add_task": lambda ds: get_daily_work_tools(ds),
    "list_tasks": lambda ds: get_daily_work_tools(ds),
    "complete_task": lambda ds: get_daily_work_tools(ds),
    "add_note": lambda ds: get_daily_work_tools(ds),
    "search_notes": lambda ds: get_daily_work_tools(ds),
    # Convenience group names
    "coding": lambda ds: get_coding_tools(ds),
    "daily_work": lambda ds: get_daily_work_tools(ds),
}
