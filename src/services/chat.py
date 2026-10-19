import logging
import time

from src.agents.graph import AgentGraph
from src.core.config import Settings
from src.core.logging import log_event
from src.models.schemas import ChatRequest, ChatResponse
from src.repositories.audit import AuditRepository
from src.repositories.conversations import ConversationRepository
from src.services.answer_cache import AnswerCache
from src.services.entitlement import EntitlementService
from src.services.followup import FollowUp
from src.services.guards import OutputGuard
from src.services.llm import LLMService, UsageMeter

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        settings: Settings,
        graph: AgentGraph,
        entitlement: EntitlementService,
        conversations: ConversationRepository,
        audit: AuditRepository,
        cache: AnswerCache,
        llm: LLMService,
        output_guard: OutputGuard,
    ) -> None:
        self.settings = settings
        self.graph = graph
        self.entitlement = entitlement
        self.conversations = conversations
        self.audit = audit
        self.cache = cache
        self.llm = llm
        self.output_guard = output_guard

    def handle(self, request: ChatRequest) -> ChatResponse:
        started = time.perf_counter()
        entitled = self.entitlement.entitled_ids(request.client_id)
        conversation_id = self.conversations.ensure(request.conversation_id, request.client_id)
        history = self.conversations.recent_user_messages(conversation_id)
        self.conversations.add_message(conversation_id, "user", request.message)

        context = history[-1] if history and FollowUp.maybe(request.message) else ""
        key = self.cache.key(request.client_id, request.message, entitled, f"{self.llm.provider}:{self.llm.model}:{self.llm.enabled}:{context}")
        response = self.cache.get(key)
        cached = response is not None
        meter = UsageMeter(cap=self.settings.request_token_cap)
        if response is None:
            state = self.graph.run({"client_id": request.client_id, "question": request.message, "history": history, "meter": meter})
            response = self._build(state, conversation_id)
            response.llm_used = bool(state.get("used_llm"))
            response.tokens_in, response.tokens_out = meter.tokens_in, meter.tokens_out
        else:
            response = response.model_copy(update={"cached": True, "tokens_in": 0, "tokens_out": 0})
        response = response.model_copy(update={"conversation_id": conversation_id})
        response.message_id = self.conversations.add_message(conversation_id, "assistant", response.answer, response.model_dump())
        if not cached:
            self.cache.put(key, response)

        latency_ms = int((time.perf_counter() - started) * 1000)
        cost = self.llm.cost(meter.tokens_in, meter.tokens_out)
        self.audit.log_usage(request.client_id, response.intent, meter.tokens_in, meter.tokens_out, cost, latency_ms, cached)
        log_event(
            logger,
            "chat",
            client_id=request.client_id,
            intent=response.intent,
            latency_ms=latency_ms,
            tokens_in=meter.tokens_in,
            tokens_out=meter.tokens_out,
            cost_usd=cost,
            cached=cached,
            escalated=response.escalated,
            confidence=response.confidence,
            flags=response.flags,
        )
        return response

    def _build(self, state: dict, conversation_id: str) -> ChatResponse:
        return ChatResponse(
            answer=self.output_guard.redact(state["answer"]),
            citations=state.get("citations", []),
            confidence=state["confidence"],
            conflicts=state.get("conflicts", []),
            derived_values=state.get("derived", []),
            escalated=state["escalated"],
            escalation_id=state.get("escalation_id"),
            intent=state["intent"].value,
            flags=state.get("flags", []),
            sql_queries=state.get("sql_queries", []),
            conversation_id=conversation_id,
            message_id=0,
        )
