"""Run only against an explicitly configured, disposable MySQL test database.

Initialize its schema first. Set TRAVEL_TEST_MYSQL=1 and MEMORY_MYSQL_* in the
test process environment; the regular .env is deliberately not loaded here.
"""
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.exceptions import ConversationBusyError, NotFoundError
from app.memory.mysql import MySQLMemoryStore
from app.memory.admin import import_sqlite
from app.memory.store import MemoryStore


pytestmark = pytest.mark.skipif(os.environ.get("TRAVEL_TEST_MYSQL") != "1", reason="Dedicated MySQL test database not configured")


def test_mysql_owner_isolation_leases_summary_and_sqlite_import(tmp_path):
    settings = Settings(_env_file=None, memory_backend="mysql", llm_provider="fake")
    assert settings.memory_mysql_database.endswith("_test"), "Only a disposable database ending in _test is allowed"
    store = MySQLMemoryStore(settings)
    store.initialize()
    owner = "user:test-" + str(uuid4())
    other = "user:test-" + str(uuid4())
    result = SimpleNamespace(output="历史建议", tool_results=[], mode="live", stopped=False)
    conversation = None
    try:
        for index in range(9):
            conversation, lease = store.begin(owner, conversation, f"南京预算{index}")
            with pytest.raises(ConversationBusyError):
                store.begin(owner, conversation, "并发请求")
            store.finish(owner, conversation, lease, f"南京预算{index}", result)
        assert len(store.conversation(owner, conversation)["summary"]) == 3
        assert len(store.history(owner, conversation)) == 12
        with pytest.raises(NotFoundError):
            store.conversation(other, conversation)
        source = MemoryStore(tmp_path / "source.sqlite3")
        source.initialize()
        cid, lease = source.begin(owner, None, "待迁移对话")
        source.finish(owner, cid, lease, "待迁移对话", result)
        assert import_sqlite(store, source.path)["imported"] == 1
        assert import_sqlite(store, source.path)["unchanged"] == 1
        assert store.conversation(owner, cid)["turns"][0]["output"] == "历史建议"
        assert source.conversation(owner, cid)["turns"][0]["output"] == "历史建议"
    finally:
        store.forget(owner)
        store.close()


def test_mysql_itinerary_persistence_and_revision_conflicts():
    from app.itineraries.store import ItineraryStore
    from app.itineraries.models import RevisionConflict
    settings = Settings(_env_file=None, memory_backend="mysql", llm_provider="fake")
    assert settings.memory_mysql_database.endswith("_test")
    memory = MySQLMemoryStore(settings)
    memory.initialize()
    store = ItineraryStore(memory)
    store.initialize()
    assert store.ready, "Initialize the latest mysql_schema.sql in the test database first"
    owner = "user:itinerary-" + str(uuid4())
    try:
        plan = store.create(owner, {"title": "持久化测试", "stops": [], "changes": []})
        reopened = ItineraryStore(MySQLMemoryStore(settings))
        reopened.initialize()
        assert reopened.get(owner, plan["id"])["title"] == "持久化测试"
        with pytest.raises(NotFoundError):
            reopened.get("user:other", plan["id"])
        store.update(owner, plan["id"], 1, {"title": "调整后", "stops": [], "changes": []})
        with pytest.raises(RevisionConflict):
            store.update(owner, plan["id"], 1, {"title": "旧版本覆盖"})
        with pytest.raises(RevisionConflict):
            store.delete(owner, plan["id"], 1)
        store.delete(owner, plan["id"], 2)
    finally:
        store.forget(owner)
        memory.close()
