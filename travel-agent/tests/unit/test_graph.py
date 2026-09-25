import pytest

from app.domain.models import ChatMessage
from app.graph.workflow import build_graph
from app.llm.fake import FakeModel


def test_graph_compiles() -> None:
    graph = build_graph(FakeModel())
    assert graph is not None
    assert {"preprocess", "agent"}.issubset(graph.get_graph().nodes)


@pytest.mark.asyncio
async def test_graph_async_invoke() -> None:
    graph = build_graph(FakeModel())
    result = await graph.ainvoke(
        {
            "request_id": "req-1",
            "conversation_id": "conv-1",
            "user_id": None,
            "messages": [ChatMessage(role="user", content="  ping  ")],
            "context": {},
            "tool_results": [],
            "metadata": {},
            "errors": [],
        }
    )
    assert result["messages"][-1].content == "Fake model response: ping"

