from app.core.exceptions import ToolError
from app.observability import Instrumentation, Timer
from app.tools.models import ToolResult
from app.tools.registry import ToolRegistry


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, instrumentation: Instrumentation) -> None:
        self._registry = registry
        self._instrumentation = instrumentation

    async def execute(self, name: str, arguments: dict) -> ToolResult:
        definition = self._registry.get(name)
        timer = Timer()
        self._instrumentation.event("tool_start", tool_name=name)
        try:
            output = await definition.handler(arguments)
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError(f"Tool '{name}' execution failed") from exc
        finally:
            self._instrumentation.event("tool_end", tool_name=name, latency_ms=timer.elapsed_ms)
        return ToolResult(tool_name=name, output=output, latency_ms=timer.elapsed_ms)

