from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.nodes import create_agent_node, preprocess
from app.graph.state import AgentState
from app.llm.base import ChatModel
from app.observability import Instrumentation, StructuredLogInstrumentation


def build_graph(
    model: ChatModel,
    instrumentation: Instrumentation | None = None,
) -> CompiledStateGraph:
    effective_instrumentation = instrumentation or StructuredLogInstrumentation()
    graph = StateGraph(AgentState)
    graph.add_node("preprocess", preprocess)
    graph.add_node("agent", create_agent_node(model, effective_instrumentation))
    graph.add_edge(START, "preprocess")
    graph.add_edge("preprocess", "agent")
    graph.add_edge("agent", END)
    return graph.compile()
