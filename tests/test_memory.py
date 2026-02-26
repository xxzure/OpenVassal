"""Tests for the DataStore and MemoryManager."""

import sqlite3
import tempfile
from pathlib import Path

import pytest
from agents.memory.sqlite_session import SQLiteSession

from openvassal.memory import MemoryManager


@pytest.fixture
def memory_mgr() -> MemoryManager:
    tmp = tempfile.mktemp(suffix=".db")
    return MemoryManager(db_path=Path(tmp))


def test_create_and_list_conversations(memory_mgr: MemoryManager):
    """Test creating and listing conversations."""
    assert len(memory_mgr.list_conversations()) == 0

    conv1 = memory_mgr.create_conversation("Chat 1")
    assert conv1["id"] is not None
    assert conv1["title"] == "Chat 1"

    conv2 = memory_mgr.create_conversation()
    assert conv2["title"] == "New Chat"

    convs = memory_mgr.list_conversations()
    assert len(convs) == 2
    # newest first
    assert convs[0]["id"] == conv2["id"]
    assert convs[1]["id"] == conv1["id"]

    # test get_conversation
    c1 = memory_mgr.get_conversation(conv1["id"])
    assert c1 is not None
    assert c1["title"] == "Chat 1"


def test_update_and_touch_conversation(memory_mgr: MemoryManager):
    """Test updating title and touch behavior."""
    conv = memory_mgr.create_conversation("Initial")
    memory_mgr.update_conversation_title(conv["id"], "Updated")

    c = memory_mgr.get_conversation(conv["id"])
    assert c["title"] == "Updated"


def test_get_or_create_session(memory_mgr: MemoryManager):
    """Test creation of SQLiteSessions."""
    conv = memory_mgr.create_conversation()
    session = memory_mgr.get_or_create_session(conv["id"])

    assert isinstance(session, SQLiteSession)
    assert session.session_id == conv["id"]

    # Calling again returns same instance
    session2 = memory_mgr.get_or_create_session(conv["id"])
    assert session is session2


def test_facts_crud(memory_mgr: MemoryManager):
    """Test saving, listing, and deleting user facts."""
    assert len(memory_mgr.get_all_facts()) == 0

    fact_id = memory_mgr.add_fact("User is testing")
    facts = memory_mgr.get_all_facts()
    assert len(facts) == 1
    assert facts[0]["fact"] == "User is testing"

    # Save list removes duplicates (case insensitive)
    memory_mgr.save_facts_from_list(["User is testing", "User likes apples", "USER IS TESTING"])
    facts = memory_mgr.get_all_facts()
    assert len(facts) == 2
    
    text = memory_mgr.get_facts_text()
    assert "testing" in text
    assert "apples" in text

    # Delete
    deleted = memory_mgr.delete_fact(fact_id)
    assert deleted
    assert len(memory_mgr.get_all_facts()) == 1


def test_delete_conversation(memory_mgr: MemoryManager):
    """Test deleting a conversation cleans up sessions."""
    conv = memory_mgr.create_conversation()
    session = memory_mgr.get_or_create_session(conv["id"])
    
    deleted = memory_mgr.delete_conversation(conv["id"])
    assert deleted
    
    assert memory_mgr.get_conversation(conv["id"]) is None
    # Session cache should be cleared
    assert conv["id"] not in memory_mgr._sessions
