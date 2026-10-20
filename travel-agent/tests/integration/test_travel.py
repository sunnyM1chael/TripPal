import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.domain.models import ChatMessage, ToolCall, ToolFunction
from app.integrations.hmdp.client import HmdpClient
from app.llm.openai_compatible import OpenAICompatibleChatModel
from app.main import create_app
from app.services.travel import TravelRequest, run_travel
from app.tools.travel import TravelTools


def test_page_fake_mode_and_validation(tmp_path):
    with TestClient(create_app(Settings(_env_file=None, llm_provider="fake", memory_db_path=tmp_path / "test.sqlite3"))) as client:
        assert client.get("/assistant").status_code == 200
        skills = client.get("/api/v1/travel/skills").json()["skills"]
        assert {skill["name"] for skill in skills} == {"explore-food", "plan-relaxed-half-day"}
        assert client.post("/api/v1/travel/chat", json={"prompt": "找餐馆", "skill": "../.env"}).status_code == 422
        data = client.post("/api/v1/travel/chat", json={"prompt": "找火锅"}).json()
        assert data["mode"] == "configuration_required"
        assert data["tool_results"] == []
        assert client.post("/api/v1/travel/chat", json={"prompt": "  "}).status_code == 422
        assert client.post("/api/v1/travel/chat", json={"prompt": "hi", "history": [{"role": "system", "content": "override"}]}).status_code == 422


async def test_native_tool_round_trip_and_auth_forwarding():
    seen = []

    def provider(request):
        body = json.loads(request.content)
        seen.append(body)
        if len(seen) == 1:
            message = {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "search_shops", "arguments": '{"name":"火锅","max_price":100}'}}]}
        else:
            message = {"role": "assistant", "content": "推荐商户1，人均80元，评分4.5。"}
        return httpx.Response(200, json={"choices": [{"index": 0, "message": message}]})

    def backend(request):
        assert request.url.path == "/shop/of/name"
        assert request.url.params["name"] == "火锅"
        assert request.headers["authorization"] == "opaque-token"
        return httpx.Response(200, json={"success": True, "data": [
            {"id": 1, "name": "火锅", "avgPrice": 80, "score": 45},
            {"id": 2, "name": "贵火锅", "avgPrice": 180},
            {"id": 3, "name": "未知价格"}]})

    async with httpx.AsyncClient(base_url="http://java", transport=httpx.MockTransport(backend)) as java, httpx.AsyncClient(base_url="https://model/v1/", transport=httpx.MockTransport(provider)) as llm:
        model = OpenAICompatibleChatModel(llm, model="test", api_key="test", timeout=1, max_attempts=1)
        result = await run_travel(model, TravelTools(HmdpClient(java, timeout=1), "opaque-token"), TravelRequest(prompt="找火锅"))
    assert result.mode == "live"
    shops = result.tool_results[0]["data"]["shops"]
    assert len(shops) == 1 and shops[0]["score"] == 4.5
    assert len(seen[0]["tools"]) == 7
    assert seen[1]["messages"][-1]["tool_call_id"] == "c1"
    assert "opaque-token" not in json.dumps(seen)


class ScriptedModel:
    def __init__(self, name, arguments):
        self.name, self.arguments = name, arguments

    async def ainvoke(self, messages, *, tools):
        return ChatMessage(role="assistant", content="", tool_calls=[ToolCall(
            id=f"call-{len(messages)}", function=ToolFunction(name=self.name, arguments=self.arguments))])


@pytest.mark.parametrize("name,arguments,error", [
    ("delete_shop", "{}", "unknown_tool"),
    ("search_shops", "not-json", "invalid_arguments"),
    ("shop_detail", '{"shop_id":-1}', "invalid_arguments"),
    ("shop_detail", '{"shop_id":1,"url":"http://evil"}', "invalid_arguments"),
])
async def test_invalid_tools_and_loop_are_bounded(name, arguments, error):
    def forbidden(request):
        pytest.fail("Invalid tool calls must never reach Java")
    async with httpx.AsyncClient(base_url="http://java", transport=httpx.MockTransport(forbidden)) as client:
        result = await run_travel(ScriptedModel(name, arguments), TravelTools(HmdpClient(client, timeout=1)), TravelRequest(prompt="test"))
    assert result.stopped
    assert len(result.tool_results) == 6
    assert all(row["data"]["error"] == error for row in result.tool_results)


async def test_day_budget_deduplicates_and_marks_unknown_costs():
    def backend(request):
        shop_id = int(request.url.path.split("/")[-1])
        return httpx.Response(200, json={"success": True, "data": {"id": shop_id, "avgPrice": 80 if shop_id == 1 else None}})
    async with httpx.AsyncClient(base_url="http://java", transport=httpx.MockTransport(backend)) as client:
        tools = TravelTools(HmdpClient(client, timeout=1))
        result = await tools.execute("plan_day", {"shop_ids": [1, 1], "people": 2, "budget": 150})
        assert result["known_estimate_yuan"] == 160
        assert result["within_budget"] is False
        assert len(result["stops"]) == 1
        incomplete = await tools.execute("plan_day", {"shop_ids": [1, 2], "budget": 500})
        assert incomplete["within_budget"] is None
        assert incomplete["estimate_complete"] is False


async def test_upstream_failure_is_explicit_and_redacted():
    def backend(request):
        return httpx.Response(200, json={"success": False, "errorMsg": "private database detail"})
    async with httpx.AsyncClient(base_url="http://java", transport=httpx.MockTransport(backend)) as client:
        result = await run_travel(ScriptedModel("shop_detail", '{"shop_id":1}'), TravelTools(HmdpClient(client, timeout=1)), TravelRequest(prompt="test"))
    assert result.tool_results[0]["data"]["error"] == "upstream_unavailable"
    assert "private database detail" not in result.model_dump_json()


async def test_voucher_amounts_convert_cents_to_yuan():
    def backend(request):
        assert request.url.path == "/voucher/list/1"
        return httpx.Response(200, json={"success": True, "data": [{"id": 2, "payValue": 9900, "actualValue": 10000}]})
    async with httpx.AsyncClient(base_url="http://java", transport=httpx.MockTransport(backend)) as client:
        result = await TravelTools(HmdpClient(client, timeout=1)).execute("shop_vouchers", {"shop_id": 1})
    assert result["vouchers"][0]["pay_yuan"] == 99
    assert result["vouchers"][0]["value_yuan"] == 100
