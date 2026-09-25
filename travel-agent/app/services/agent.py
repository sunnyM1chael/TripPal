from app.domain.models import AgentExecutionRequest, AgentExecutionResult
from app.services.runtime import AgentRuntime


class AgentService:
    def __init__(self, runtime: AgentRuntime) -> None:
        self._runtime = runtime

    async def run(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        return await self._runtime.run(request)

