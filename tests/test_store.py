"""Tests for the data store."""

import tempfile
from pathlib import Path

from openvassal.data.store import DataStore
from openvassal.models import DataCategory, DataRecord


def _make_store() -> DataStore:
    tmp = tempfile.mktemp(suffix=".db")
    return DataStore(db_path=Path(tmp))


def test_save_and_get():
    store = _make_store()
    record = DataRecord(
        category=DataCategory.DAILY,
        source="test",
        title="Test record",
        content="Hello world",
    )
    saved = store.save(record)
    assert saved.id is not None

    fetched = store.get(saved.id)
    assert fetched is not None
    assert fetched.title == "Test record"
    assert fetched.content == "Hello world"


def test_query_by_category():
    store = _make_store()
    store.save(DataRecord(category=DataCategory.DAILY, source="a", title="Daily task"))
    store.save(DataRecord(category=DataCategory.HEALTH, source="b", title="Health record"))
    store.save(DataRecord(category=DataCategory.FINANCIAL, source="c", title="Expense"))

    daily = store.query(category=DataCategory.DAILY)
    assert len(daily) == 1
    assert daily[0].title == "Daily task"

    health = store.query(category=DataCategory.HEALTH)
    assert len(health) == 1


def test_query_search():
    store = _make_store()
    store.save(DataRecord(category=DataCategory.DAILY, source="test", title="Buy groceries"))
    store.save(DataRecord(category=DataCategory.DAILY, source="test", title="Fix the car"))

    results = store.query(search="groceries")
    assert len(results) == 1
    assert "groceries" in results[0].title


def test_delete():
    store = _make_store()
    record = store.save(
        DataRecord(category=DataCategory.CHAT, source="test", title="To delete")
    )
    assert store.get(record.id) is not None

    result = store.delete(record.id)
    assert result is True
    assert store.get(record.id) is None


def test_delete_nonexistent():
    store = _make_store()
    assert store.delete("nonexistent") is False


def test_stats():
    store = _make_store()
    store.save(DataRecord(category=DataCategory.DAILY, source="a", title="1"))
    store.save(DataRecord(category=DataCategory.DAILY, source="a", title="2"))
    store.save(DataRecord(category=DataCategory.HEALTH, source="b", title="3"))

    stats = store.stats
    assert stats["daily"] == 2
    assert stats["health"] == 1


def test_metadata_roundtrip():
    store = _make_store()
    record = store.save(
        DataRecord(
            category=DataCategory.FINANCIAL,
            source="test",
            title="Expense",
            metadata={"amount": 42.50, "currency": "USD", "tags": ["food"]},
        )
    )
    fetched = store.get(record.id)
    assert fetched.metadata["amount"] == 42.50
    assert fetched.metadata["currency"] == "USD"
    assert "food" in fetched.metadata["tags"]
