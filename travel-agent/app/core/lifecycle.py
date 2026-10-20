from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
import asyncio

import httpx
from fastapi import FastAPI

from app.container import ApplicationContainer
from app.core.config import Settings
from app.graph.workflow import build_graph
from app.integrations.hmdp.client import HmdpClient
from app.llm.factory import create_chat_model
from app.observability import StructuredLogInstrumentation
from app.services.agent import AgentService
from app.services.runtime import AgentRuntime
from app.tools.executor import ToolExecutor
from app.tools.models import ToolDefinition
from app.tools.registry import ToolRegistry
from app.integrations.amap import AmapClient
from app.memory.factory import create_memory
from app.integrations.hmdp.preferences import PreferenceGateway


async def echo(arguments: dict[str, Any]) -> Any:
    return arguments.get("value")


def create_lifespan(settings: Settings):
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        instrumentation = StructuredLogInstrumentation()
        memory = create_memory(settings)
        await asyncio.to_thread(memory.initialize, settings.memory_retention_days)
        hmdp_http_client = httpx.AsyncClient(base_url=str(settings.hmdp_base_url))
        maps_http_client = httpx.AsyncClient(base_url="https://restapi.amap.com", follow_redirects=False)
        llm_http_client = None
        provider = settings.llm_provider.lower().replace("-", "_")
        if provider in {"openai", "openai_compatible"}:
            llm_http_client = httpx.AsyncClient(base_url=f"{str(settings.llm_base_url).rstrip('/')}/")
        tools = ToolRegistry()
        tools.register(ToolDefinition(name="echo", description="Return a value for platform validation", handler=echo))
        llm = create_chat_model(settings, llm_http_client)
        graph = build_graph(llm, instrumentation)
        runtime = AgentRuntime(graph, instrumentation)
        app.state.container = ApplicationContainer(
            settings=settings,
            hmdp_http_client=hmdp_http_client,
            llm_http_client=llm_http_client,
            hmdp_client=HmdpClient(hmdp_http_client, timeout=settings.hmdp_timeout),
            llm=llm,
            tools=tools,
            tool_executor=ToolExecutor(tools, instrumentation),
            runtime=runtime,
            agent_service=AgentService(runtime),
            memory=memory,
            preferences=PreferenceGateway(HmdpClient(hmdp_http_client, timeout=settings.hmdp_timeout)),
            maps=AmapClient(maps_http_client, settings.amap_api_key.get_secret_value() if settings.amap_api_key else None,
                            settings.amap_timeout),
        )
        try:
            yield
        finally:
            app.state.container.initialized = False
            await asyncio.to_thread(memory.close)
            await hmdp_http_client.aclose()
            await maps_http_client.aclose()
            if llm_http_client is not None:
                await llm_http_client.aclose()

    return lifespan
