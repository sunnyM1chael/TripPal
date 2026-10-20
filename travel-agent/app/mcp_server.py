"""Local, read-only MCP adapter. Run with python -m app.mcp_server."""
import asyncio
import json
import sys
from contextlib import asynccontextmanager

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations
from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.integrations.amap import AmapClient
from app.integrations.hmdp.client import HmdpClient
from app.tools.travel import DEFINITIONS, MAP_DEFINITIONS, TravelTools


# Deliberately exclude account memory, credentials, writes and arbitrary HTTP requests.
READ_TOOL_NAMES = (
    "list_categories", "search_shops", "shops_by_category", "shop_detail", "shop_vouchers",
    "plan_day", "search_cities", "search_city_places", "plan_route",
)
READ_TOOLS = {name: {**DEFINITIONS, **MAP_DEFINITIONS}[name] for name in READ_TOOL_NAMES}


async def invoke_read_tool(tools: TravelTools, name: str, arguments: dict) -> CallToolResult:
    if name not in READ_TOOLS:
        data, failed = {"error": "unknown_tool", "message": "未开放此工具。"}, True
    else:
        try:
            # Validate even when called outside an MCP transport.
            READ_TOOLS[name][0].model_validate(arguments)
            async with asyncio.timeout(30):
                data = await tools.execute(name, arguments)
            failed = bool(data.get("error"))
        except (ValueError, TypeError, ValidationError):
            data, failed = {"error": "invalid_arguments", "message": "参数不符合工具定义。"}, True
        except AppError as exc:
            data, failed = {"error": exc.code, "message": "查询服务暂不可用，请检查本机服务与配置。"}, True
        except TimeoutError:
            data, failed = {"error": "timeout", "message": "查询超时，请缩小范围重试。"}, True
        except Exception:
            # Do not expose upstream URLs, API keys or internal exception details to clients.
            data, failed = {"error": "internal_error", "message": "查询失败，请检查服务端状态。"}, True
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(data, ensure_ascii=False))],
                          structuredContent=data, isError=failed)


def create_server(injected_tools: TravelTools | None = None) -> Server:
    @asynccontextmanager
    async def lifespan(server):
        if injected_tools is not None:
            yield injected_tools
            return
        settings = Settings()
        async with httpx.AsyncClient(base_url=str(settings.hmdp_base_url)) as java, \
                httpx.AsyncClient(base_url="https://restapi.amap.com", follow_redirects=False) as maps:
            yield TravelTools(HmdpClient(java, timeout=settings.hmdp_timeout), maps=AmapClient(
                maps, settings.amap_api_key.get_secret_value() if settings.amap_api_key else None,
                settings.amap_timeout))

    server = Server("trippal-readonly", lifespan=lifespan)

    @server.list_tools()
    async def list_tools():
        return [Tool(name=name, description=description, inputSchema=schema.model_json_schema(),
                     annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                                                 idempotentHint=True, openWorldHint=True))
                for name, (schema, description) in READ_TOOLS.items()]

    @server.call_tool()
    async def call_tool(name, arguments):
        return await invoke_read_tool(server.request_context.lifespan_context, name, arguments)

    return server


async def main():
    # stdout belongs exclusively to JSON-RPC in stdio mode.
    configure_logging("WARNING", stream=sys.stderr)
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
