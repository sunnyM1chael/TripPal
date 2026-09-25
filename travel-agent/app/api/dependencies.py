from fastapi import Request

from app.container import ApplicationContainer
from app.services.agent import AgentService


def get_container(request: Request) -> ApplicationContainer:
    return request.app.state.container


def get_agent_service(request: Request) -> AgentService:
    return get_container(request).agent_service

