"""Coding Agent — code generation, review, debugging, and technical help.

This is a v1 sub-agent that demonstrates the plugin pattern.
"""

from __future__ import annotations

from agents import Agent, function_tool

from subordinates.agents.base import BaseAgent
from subordinates.models import DataCategory, DataRecord


class CodingAgent(BaseAgent):
    """Sub-agent specialized in coding tasks."""

    name = "Coding Agent"
    description = "Code generation, review, debugging, and technical assistance"

    def build_agent(self) -> Agent:
        return Agent(
            name=self.name,
            instructions=(
                "You are a senior software engineer. Help the user with:\n"
                "- Writing code in any language\n"
                "- Code review and best practices\n"
                "- Debugging and troubleshooting\n"
                "- Architecture and design decisions\n"
                "- Explaining technical concepts\n\n"
                "Always provide clean, well-documented code. "
                "When generating code, include comments and explain your approach."
            ),
            model=self.model,
            tools=self.get_tools(),
        )

    def get_tools(self) -> list:
        store = self.data_store

        @function_tool
        def save_code_snippet(title: str, language: str, code: str) -> str:
            """Save a code snippet to the personal knowledge base for later reference."""
            record = DataRecord(
                category=DataCategory.DAILY,
                source="coding_agent",
                title=f"[{language}] {title}",
                content=code,
                metadata={"language": language, "type": "code_snippet"},
            )
            store.save(record)
            return f"Saved code snippet '{title}' ({language})"

        @function_tool
        def search_saved_code(query: str) -> str:
            """Search previously saved code snippets."""
            results = store.query(search=query, limit=5)
            if not results:
                return "No saved code snippets found matching your query."
            lines = []
            for r in results:
                lines.append(f"### {r.title}\n```\n{r.content[:500]}\n```\n")
            return "\n".join(lines)

        return [save_code_snippet, search_saved_code]
