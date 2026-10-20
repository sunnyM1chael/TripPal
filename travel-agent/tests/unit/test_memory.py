from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.exceptions import ConversationBusyError, NotFoundError, RequestLimitError
from app.integrations.amap import Point, RouteRequest, navigation_url, parse_point, AmapClient
from app.memory.models import Preferences
from app.memory.store import MemoryStore


@pytest.fixture
def memory(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()
    return store


def response(output="根据您的预算安排", tools=None):
    return SimpleNamespace(output=output, tool_results=tools or [], mode="live", stopped=False)


def test_preferences_survive_restart_and_are_owner_scoped(memory):
    memory.update_preferences("user:1", {"default_city": "南京", "budget_per_person": 120, "cuisines": ["淮扬菜"]})
    restarted = MemoryStore(memory.path)
    restarted.initialize()
    assert restarted.preferences("user:1")["budget_per_person"] == 120
    assert restarted.preferences("user:2") == {}
    restarted.update_preferences("user:1", {"budget_per_person": None})
    assert "budget_per_person" not in restarted.preferences("user:1")
    assert restarted.preferences("user:1")["default_city"] == "南京"


def test_conversation_restores_history_tools_and_prevents_idor(memory):
    conversation, lease = memory.begin("user:1", None, "南京火锅")
    memory.finish("user:1", conversation, lease, "南京火锅", response(tools=[{"tool": "search_city_places", "data": {"places": [{"poi_id": "B123456"}]}}]))
    restored = MemoryStore(memory.path).conversation("user:1", conversation)
    assert restored["turns"][0]["tools"][0]["data"]["places"][0]["poi_id"] == "B123456"
    assert len(memory.history("user:1", conversation)) == 2
    assert memory.list_conversations("user:2") == []
    for operation in [memory.conversation, memory.delete_conversation]:
        with pytest.raises(NotFoundError):
            operation("user:2", conversation)
    with pytest.raises(NotFoundError):
        memory.begin("user:2", conversation, "steal")


def test_lease_is_atomic_and_failure_release_allows_retry(memory):
    conversation, lease = memory.begin("user:1", None, "hello")
    with pytest.raises(ConversationBusyError):
        memory.begin("user:1", conversation, "duplicate")
    memory.release("user:1", conversation, "wrong-lease")
    with pytest.raises(ConversationBusyError):
        memory.begin("user:1", conversation, "still busy")
    memory.release("user:1", conversation, lease)
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = [pool.submit(memory.begin, "user:1", conversation, "concurrent") for _ in range(2)]
        outcomes = []
        for task in tasks:
            try:
                outcomes.append(task.result())
            except ConversationBusyError:
                pass
    assert len(outcomes) == 1


def test_recall_and_forget_only_affect_current_owner(memory):
    memory.update_preferences("a", {"default_city": "南京"})
    for owner in ["a", "b"]:
        conv, lease = memory.begin(owner, None, "南京火锅预算")
        memory.finish(owner, conv, lease, "南京火锅预算100元", response("火锅安排"))
    hits = memory.recall("a", "南京火锅", "new-id")
    assert len(hits) == 1
    memory.forget("a")
    assert memory.preferences("a") == {}
    assert memory.list_conversations("a") == []
    assert len(memory.list_conversations("b")) == 1


def test_forget_rejects_inflight_turn(memory):
    conversation, lease = memory.begin("a", None, "hello")
    with pytest.raises(ConversationBusyError):
        memory.forget("a")
    memory.release("a", conversation, lease)
    memory.forget("a")
    with pytest.raises(NotFoundError):
        memory.conversation("a", conversation)


def test_rate_limit_is_per_owner(memory):
    memory.check_rate("a", 2)
    memory.check_rate("a", 2)
    with pytest.raises(RequestLimitError):
        memory.check_rate("a", 2)
    memory.check_rate("b", 2)


def test_older_turns_are_summarized_and_summary_survives_restart(memory):
    conversation = None
    for index in range(12):
        prompt = f"第{index}轮：南京旅行预算100元"
        conversation, lease = memory.begin("user:1", conversation, prompt)
        memory.finish("user:1", conversation, lease, prompt, response("历史建议"))
    restarted = MemoryStore(memory.path)
    restarted.initialize()
    data = restarted.conversation("user:1", conversation)
    assert len(data["summary"]) == 6
    assert data["summary"][0]["user_request"].startswith("第0轮")
    assert len(restarted.history("user:1", conversation)) == 12
    assert restarted.history("user:1", conversation)[0]["content"].startswith("第6轮")
    restarted.delete_conversation("user:1", conversation)
    with pytest.raises(NotFoundError):
        restarted.conversation("user:1", conversation)


@pytest.mark.parametrize("patch", [{"budget_per_person": -1}, {"budget_per_person": float("inf")}, {"unknown": "bad"}, {"cuisines": ["x" * 61]}])
def test_preferences_reject_invalid_values(patch):
    with pytest.raises(ValidationError):
        Preferences.model_validate(patch)


def test_coordinates_and_navigation_are_validated():
    assert parse_point("118.8,32.1").coordinate() == "118.800000,32.100000"
    assert parse_point("NaN,32") is None
    assert parse_point("181,90") is None
    assert parse_point([]) is None
    with pytest.raises(ValidationError):
        RouteRequest(origin_poi_id="http://evil", destination_poi_id="B12345")
    link = navigation_url({"name": "店铺&foo=bar", "location": "118.8,32.1"})
    assert link.startswith("https://uri.amap.com/navigation?")
    assert "&foo=" not in link
    assert "key=" not in link


def test_place_namespace_and_currency_normalization():
    place = AmapClient.place({"id": "B123456", "name": "测试地点", "location": "118.8,32.1", "biz_ext": {"rating": "4.5", "cost": "100"}})
    assert place["poi_id"] == "B123456"
    assert "id" not in place and "shopId" not in place
    assert place["cost_yuan"] == 100


def test_remember_requires_an_affirmative_request():
    from app.api.travel_routes import may_remember
    assert may_remember("记住，我喜欢淮扬菜，人均预算100元")
    assert not may_remember("不要记住我的预算")
    assert not may_remember("你上次记住了什么？")
