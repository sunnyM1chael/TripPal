import httpx
import pytest
from importlib.util import find_spec

if find_spec("mcp") is None:
    pytest.skip("Install requirements-mcp.txt for MCP protocol tests", allow_module_level=True)
from mcp.shared.memory import create_connected_server_and_client_session

from app.core.exceptions import IntegrationError
from app.integrations.hmdp.client import HmdpClient
from app.mcp_server import READ_TOOLS, create_server, invoke_read_tool
from app.tools.travel import TravelTools


async def test_mcp_protocol_initialize_discover_and_query():
    requests = []

    def backend(request):
        requests.append(request)
        assert request.method == "GET"
        assert request.url.path == "/shop-type/list"
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"success": True, "data": [{"id": 1, "name": "美食"}]})

    async with httpx.AsyncClient(base_url="http://java", transport=httpx.MockTransport(backend)) as java:
        server = create_server(TravelTools(HmdpClient(java, timeout=1)))
        # Real SDK sessions and JSON-RPC over in-memory streams; no network or keys.
        async with create_connected_server_and_client_session(server) as session:
            resources = await session.list_resources()
            assert "trippal://guide/capabilities" in {str(r.uri) for r in resources.resources}
            guide = await session.read_resource("trippal://guide/capabilities")
            assert "plan_route" in guide.contents[0].text
            prompts = await session.list_prompts()
            assert "arrival-first-stop" in {p.name for p in prompts.prompts}
            prompt = await session.get_prompt("replan-remaining", {"request": "走累了，少走一点"})
            assert "get_current_itinerary" in prompt.messages[0].content.text
            listing = await session.list_tools()
            assert {t.name for t in listing.tools} == set(READ_TOOLS)
            assert all(t.annotations.readOnlyHint for t in listing.tools)
            result = await session.call_tool("list_categories", {})
            assert not result.isError
            assert result.structuredContent == {"categories": [{"id": 1, "name": "美食"}]}
            invalid = await session.call_tool("shop_detail", {"shop_id": -1})
            assert invalid.isError
            blocked = await session.call_tool("remember_preferences", {"budget_per_person": 100})
            assert blocked.isError
    assert len(requests) == 1


async def test_mcp_rejects_private_and_arbitrary_operations():
    class NeverExecute:
        async def execute(self, name, arguments):
            pytest.fail("Blocked tool must never execute")

    for name, arguments in [("remember_preferences", {}), ("read_memory", {"user_id": 1}),
                            ("http_request", {"url": "http://evil"}),
                            ("shop_detail", {"shop_id": 1, "user_id": 2})]:
        result = await invoke_read_tool(NeverExecute(), name, arguments)
        assert result.isError


async def test_mcp_redacts_upstream_errors():
    class FailingTools:
        async def execute(self, name, arguments):
            raise IntegrationError("api-key=private-value")

    result = await invoke_read_tool(FailingTools(), "list_categories", {})
    assert result.isError
    assert "private-value" not in result.model_dump_json()
