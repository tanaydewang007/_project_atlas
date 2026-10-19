from langgraph.graph import END, StateGraph

from src.agents.nodes.calculator import CalculatorNode
from src.agents.nodes.critic import CriticNode
from src.agents.nodes.escalation import EscalationNode
from src.agents.nodes.retriever import RetrieverNode
from src.agents.nodes.router import RouterNode
from src.agents.nodes.writer import WriterNode
from src.agents.state import AgentState
from src.models.domain import Intent


class AgentGraph:
    def __init__(
        self,
        router: RouterNode,
        retriever: RetrieverNode,
        calculator: CalculatorNode,
        writer: WriterNode,
        critic: CriticNode,
        escalation: EscalationNode,
    ) -> None:
        graph = StateGraph(AgentState)
        for name, node in [
            ("router", router),
            ("retriever", retriever),
            ("calculator", calculator),
            ("writer", writer),
            ("critic", critic),
            ("escalation", escalation),
        ]:
            graph.add_node(name, node)
        graph.set_entry_point("router")
        graph.add_conditional_edges("router", self._after_router, {"retriever": "retriever", "writer": "writer"})
        graph.add_conditional_edges("retriever", self._after_retriever, {"calculator": "calculator", "writer": "writer"})
        graph.add_edge("calculator", "writer")
        graph.add_edge("writer", "critic")
        graph.add_conditional_edges("critic", self._after_critic, {"writer": "writer", "escalation": "escalation"})
        graph.add_edge("escalation", END)
        self.app = graph.compile()

    @staticmethod
    def _after_router(state: dict) -> str:
        direct = state.get("refusal") or state["intent"] in (Intent.UNSAFE, Intent.OUT_OF_SCOPE, Intent.ESCALATE, Intent.GREETING)
        return "writer" if direct else "retriever"

    @staticmethod
    def _after_retriever(state: dict) -> str:
        if state.get("refusal"):
            return "writer"
        return "calculator" if state["intent"] == Intent.CALCULATION else "writer"

    @staticmethod
    def _after_critic(state: dict) -> str:
        return "writer" if state.get("deterministic") and state.get("used_llm") else "escalation"

    def run(self, state: dict) -> dict:
        return self.app.invoke(state)
