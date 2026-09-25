import pytest

from app.core.exceptions import AgentError
from app.domain.models import AgentExecutionRequest
from app.observability import StructuredLogInstrumentation
from app.services.runtime import AgentRuntime


class SuccessfulGraph:
    async def ainvoke(self, state: dict) -> dict:
        state["messages"].append({"role": "assistant", "content": "done"})
        return state


class FailingGraph:
    async def ainvoke(self, state: dict) -> dict:
        raise RuntimeError("internal detail")


def request() -> AgentExecutionRequest:
    return AgentExecutionRequest(
        prompt="run",
        request_id="req-1",
        conversation_id="conv-1",
    )


@pytest.mark.asyncio
async def test_runtime_successful_execution() -> None:
    result = await AgentRuntime(SuccessfulGraph(), StructuredLogInstrumentation()).run(request())
    assert result.output == "done"
    assert result.request_id == "req-1"


@pytest.mark.asyncio
async def test_runtime_wraps_unexpected_graph_error() -> None:
    runtime = AgentRuntime(FailingGraph(), StructuredLogInstrumentation())
    with pytest.raises(AgentError, match="graph execution failed"):
        await runtime.run(request())

