import logging

from src.core.errors import LLMUnavailable
from src.core.logging import log_event
from src.services.llm import LLMService

logger = logging.getLogger(__name__)


class BaseNode:
    def __init__(self, llm: LLMService) -> None:
        self.llm = llm

    def ask_llm(self, state: dict, system: str, user: str) -> str | None:
        meter = state["meter"]
        if not self.llm.enabled or meter.exhausted:
            return None
        try:
            result = self.llm.complete(system, user)
        except LLMUnavailable as exc:
            log_event(logger, "llm_failed", error=str(exc))
            return None
        meter.add(result)
        return result.text.strip()
