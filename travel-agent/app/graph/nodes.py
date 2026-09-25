from app.graph.state import AgentState
from app.llm.base import ChatModel
from app.observability import Instrumentation, Timer


async def preprocess(state: AgentState) -> dict:
    messages = [message.model_copy(update={"content": message.content.strip()}) for message in state["messages"]]
    return {"messages": messages}


def create_agent_node(model: ChatModel, instrumentation: Instrumentation):
    async def agent(state: AgentState) -> dict:
        timer = Timer()
        instrumentation.event("llm_start")
        try:
            response = await model.ainvoke(state["messages"])
            return {"messages": [*state["messages"], response]}
        finally:
            instrumentation.event("llm_end", latency_ms=timer.elapsed_ms)

    return agent
