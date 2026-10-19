from src.agents.nodes.base import BaseNode
from src.models.domain import Intent
from src.repositories.escalations import EscalationRepository
from src.services.llm import LLMService


class EscalationNode(BaseNode):
    def __init__(self, llm: LLMService, repo: EscalationRepository, threshold: float) -> None:
        super().__init__(llm)
        self.repo = repo
        self.threshold = threshold

    def __call__(self, state: dict) -> dict:
        confidence = state["confidence"]
        reason = state.get("force_escalate")
        if reason is None and state.get("critic_issues"):
            reason = "answer contained figures that could not be verified against a citation"
        if reason is None and confidence < self.threshold:
            reason = f"confidence {confidence:.2f} is below the {self.threshold:.2f} threshold"
        if reason is None:
            return {"answer": state["draft"], "escalated": False, "escalation_id": None}
        ticket = self.repo.create(state["client_id"], state["question"], reason, confidence)
        if state["intent"] == Intent.ESCALATE:
            tail = f"I've created ticket #{ticket} and an analyst will reply to you."
        else:
            tail = f"I'm not confident enough to answer this on my own, so I've created ticket #{ticket} and an analyst will reply to you."
        return {"answer": f"{state['draft']}\n\n{tail}", "escalated": True, "escalation_id": ticket}
