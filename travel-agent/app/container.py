from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.integrations.hmdp.client import HmdpClient
from app.llm.base import ChatModel
from app.services.agent import AgentService
from app.services.runtime import AgentRuntime
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry
from app.integrations.amap import AmapClient
from app.memory.repository import ConversationRepository
from app.integrations.hmdp.preferences import PreferenceGateway
from app.itineraries.service import ItineraryService
from app.services.voucher_subscription import VoucherSubscriptions


@dataclass(slots=True)
class ApplicationContainer:
    settings: Settings
    hmdp_http_client: httpx.AsyncClient
    llm_http_client: httpx.AsyncClient | None
    hmdp_client: HmdpClient
    llm: ChatModel
    tools: ToolRegistry
    tool_executor: ToolExecutor
    runtime: AgentRuntime
    agent_service: AgentService
    memory: ConversationRepository
    preferences: PreferenceGateway
    maps: AmapClient
    itineraries: ItineraryService | None = None
    subscriptions: VoucherSubscriptions | None = None
    initialized: bool = True
