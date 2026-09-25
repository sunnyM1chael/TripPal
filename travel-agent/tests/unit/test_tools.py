import pytest

from app.core.exceptions import ToolError
from app.observability import StructuredLogInstrumentation
from app.tools.executor import ToolExecutor
from app.tools.models import ToolDefinition
from app.tools.registry import ToolRegistry


async def echo(arguments: dict) -> object:
    return arguments["value"]


async def fail(arguments: dict) -> object:
    raise ValueError("secret implementation detail")


def definition(name: str = "echo", handler=echo) -> ToolDefinition:
    return ToolDefinition(name=name, description="test tool", handler=handler)


def test_register_and_lookup_tool() -> None:
    registry = ToolRegistry()
    registry.register(definition())
    assert registry.get("echo").name == "echo"
    assert registry.names() == ("echo",)


def test_duplicate_registration_fails() -> None:
    registry = ToolRegistry()
    registry.register(definition())
    with pytest.raises(ToolError, match="already registered"):
        registry.register(definition())


def test_missing_tool_fails() -> None:
    with pytest.raises(ToolError, match="not registered"):
        ToolRegistry().get("missing")


@pytest.mark.asyncio
async def test_execute_tool() -> None:
    registry = ToolRegistry()
    registry.register(definition())
    result = await ToolExecutor(registry, StructuredLogInstrumentation()).execute("echo", {"value": 42})
    assert result.output == 42
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_execution_error_is_mapped() -> None:
    registry = ToolRegistry()
    registry.register(definition("fail", fail))
    with pytest.raises(ToolError, match="execution failed"):
        await ToolExecutor(registry, StructuredLogInstrumentation()).execute("fail", {})

