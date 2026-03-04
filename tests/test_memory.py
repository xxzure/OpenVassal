"""Tests for the mem0-based MemoryManager."""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from openvassal.memory import MemoryManager


@pytest.fixture
def memory_mgr() -> MemoryManager:
    """Create a MemoryManager with a temp DB and mocked mem0."""
    tmp = tempfile.mktemp(suffix=".db")
    mgr = MemoryManager(db_path=Path(tmp), user_id="test_user")
    return mgr


# ── Conversation tests (SQLite-backed, no mocks needed) ──

def test_create_and_list_conversations(memory_mgr: MemoryManager):
    assert len(memory_mgr.list_conversations()) == 0

    conv1 = memory_mgr.create_conversation("Chat 1", agent_name="coder")
    assert conv1["id"] is not None
    assert conv1["title"] == "Chat 1"
    assert conv1["agent_name"] == "coder"

    conv2 = memory_mgr.create_conversation()
    assert conv2["title"] == "New Chat"

    convs = memory_mgr.list_conversations()
    assert len(convs) == 2
    assert convs[0]["id"] == conv2["id"]  # newest first
    assert convs[1]["id"] == conv1["id"]


def test_get_conversation(memory_mgr: MemoryManager):
    conv = memory_mgr.create_conversation("Test")
    result = memory_mgr.get_conversation(conv["id"])
    assert result is not None
    assert result["title"] == "Test"


def test_update_conversation_title(memory_mgr: MemoryManager):
    conv = memory_mgr.create_conversation("Initial")
    memory_mgr.update_conversation_title(conv["id"], "Updated")

    result = memory_mgr.get_conversation(conv["id"])
    assert result["title"] == "Updated"


def test_touch_conversation(memory_mgr: MemoryManager):
    conv = memory_mgr.create_conversation("Test")
    old_updated = conv["updated_at"]

    import time
    time.sleep(0.01)
    memory_mgr.touch_conversation(conv["id"])

    result = memory_mgr.get_conversation(conv["id"])
    assert result["updated_at"] >= old_updated


def test_delete_conversation(memory_mgr: MemoryManager):
    conv = memory_mgr.create_conversation("To Delete")
    assert memory_mgr.delete_conversation(conv["id"]) is True
    assert memory_mgr.get_conversation(conv["id"]) is None
    # Double delete returns False
    assert memory_mgr.delete_conversation(conv["id"]) is False


def test_get_nonexistent_conversation(memory_mgr: MemoryManager):
    assert memory_mgr.get_conversation("nonexistent") is None


# ── mem0 Memory tests (mocked) ──

def test_add_memory_with_mock(memory_mgr: MemoryManager):
    mock_mem0 = MagicMock()
    mock_mem0.add.return_value = {"id": "mem_123", "memory": "User likes Python"}
    memory_mgr._mem0 = mock_mem0

    result = memory_mgr.add_memory("User likes Python", agent_id="coder")
    assert result is not None
    mock_mem0.add.assert_called_once_with(
        "User likes Python",
        user_id="test_user",
        agent_id="coder",
        metadata={},
    )


def test_search_memory_with_mock(memory_mgr: MemoryManager):
    mock_mem0 = MagicMock()
    mock_mem0.search.return_value = {
        "results": [
            {"memory": "User works on search", "score": 0.95},
            {"memory": "User uses Python", "score": 0.80},
        ]
    }
    memory_mgr._mem0 = mock_mem0

    results = memory_mgr.search_memory("search")
    assert len(results) == 2
    assert results[0]["memory"] == "User works on search"


def test_get_all_memories_with_mock(memory_mgr: MemoryManager):
    mock_mem0 = MagicMock()
    mock_mem0.get_all.return_value = {
        "results": [
            {"id": "1", "memory": "Fact 1"},
            {"id": "2", "memory": "Fact 2"},
        ]
    }
    memory_mgr._mem0 = mock_mem0

    results = memory_mgr.get_all_memories()
    assert len(results) == 2


def test_delete_memory_with_mock(memory_mgr: MemoryManager):
    mock_mem0 = MagicMock()
    memory_mgr._mem0 = mock_mem0

    assert memory_mgr.delete_memory("mem_123") is True
    mock_mem0.delete.assert_called_once_with("mem_123")


def test_get_memory_context_with_results(memory_mgr: MemoryManager):
    mock_mem0 = MagicMock()
    mock_mem0.search.return_value = {
        "results": [
            {"memory": "User is a backend engineer"},
            {"memory": "User uses Redis"},
        ]
    }
    memory_mgr._mem0 = mock_mem0

    context = memory_mgr.get_memory_context(query="engineering")
    assert "backend engineer" in context
    assert "Redis" in context


def test_get_memory_context_empty(memory_mgr: MemoryManager):
    mock_mem0 = MagicMock()
    mock_mem0.search.return_value = {"results": []}
    memory_mgr._mem0 = mock_mem0

    context = memory_mgr.get_memory_context(query="nonexistent")
    assert context == "(No relevant memories found)"


def test_save_interaction_with_mock(memory_mgr: MemoryManager):
    mock_mem0 = MagicMock()
    memory_mgr._mem0 = mock_mem0

    memory_mgr.save_interaction(
        user_message="How does Redis work?",
        assistant_response="Redis is an in-memory data store...",
        agent_id="gemini_chat",
    )

    mock_mem0.add.assert_called_once()
    call_args = mock_mem0.add.call_args
    assert call_args[1]["user_id"] == "test_user"
    assert call_args[1]["agent_id"] == "gemini_chat"


def test_mem0_init_failure_graceful(memory_mgr: MemoryManager):
    """When mem0 fails to initialize, memory operations should return empty/None."""
    # Don't set _mem0, and patch the import to fail
    memory_mgr._mem0 = None
    with patch("openvassal.memory.MemoryManager._get_mem0", return_value=None):
        assert memory_mgr.add_memory("test") is None
        assert memory_mgr.search_memory("test") == []
        assert memory_mgr.get_all_memories() == []
        assert memory_mgr.delete_memory("test") is False
