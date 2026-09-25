from typing import Any, Protocol

from app.core.exceptions import AgentError, AppError
from app.domain.models import AgentExecutionRequest, AgentExecutionResult, ChatMessage
from app.observability import Instrumentation, Timer


class AsyncGraph(Protocol):
    async def ainvoke(self, input: dict[str, Any]) -> dict[str, Any]: ...


class AgentRuntime:
    """Stable execution boundary for graphs, future streaming, and checkpointing."""

    def __init__(self, graph: AsyncGraph, instrumentation: Instrumentation) -> None:
        self._graph = graph
        self._instrumentation = instrumentation

    async def run(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        timer = Timer()
        self._instrumentation.event("agent_start")
        state = {
            "request_id": request.request_id,
            "conversation_id": request.conversation_id,
            "user_id": request.user_id,
            "messages": [ChatMessage(role="user", content=request.prompt)],
            "context": {},
            "tool_results": [],
            "metadata": request.metadata,
            "errors": [],
        }
        try:
            result = await self._graph.ainvoke(state)
            messages = [
                message if isinstance(message, ChatMessage) else ChatMessage.model_validate(message)
                for message in result["messages"]
            ]
            output = messages[-1].content
            return AgentExecutionResult(
                request_id=request.request_id,
                conversation_id=request.conversation_id,
                output=output,
                messages=messages,
                metadata=result.get("metadata", {}),
            )
        except AppError:
            raise
        except Exception as exc:
            raise AgentError("Agent graph execution failed") from exc
        finally:
            self._instrumentation.event("agent_end", latency_ms=timer.elapsed_ms)

