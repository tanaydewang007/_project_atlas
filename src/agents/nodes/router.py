import re

from src.agents.nodes.base import BaseNode
from src.core.logging import log_event
from src.models.domain import Intent
from src.repositories.audit import AuditRepository
from src.repositories.clients import ClientRepository
from src.repositories.reports import ReportRepository
from src.services.entitlement import EntitlementService
from src.services.followup import FollowUp
from src.services.injection_guard import InjectionGuard
from src.services.llm import LLMService
from src.services.question_parser import QuestionParser
from src.services.sql_planner import SqlPlanner
import logging

logger = logging.getLogger(__name__)


class RouterNode(BaseNode):
    POLITICS = re.compile(r"election|\bvote\b|voting|president|prime minister|politic|parliament|congress|democrat|republican", re.I)
    PRIVACY = re.compile(
        r"\b(e-?mail|phone|mobile|contact (details|info|information|number|address)|home address|salary|passport|aadhaar|ssn)\b|other clients?|another client|other customers?|who (else )?(bought|purchased)|purchased by|bought by|\b(customers?|clients?)\b.{0,30}\b(contact|address|phone|details|data|list)\b",
        re.I,
    )
    DOMAIN = re.compile(
        r"market|report|cagr|size|forecast|sector|industr|water|meter|purifier|charging|sensor|iot|cyber|cloud|revenue|growth|publisher|library|trust|reliable|analyst|share|region|apac|vendor|competit|worth|valued|upgrade|access|purchase|escalat",
        re.I,
    )
    ESCALATE = re.compile(r"\b(analyst|human|escalate|(speak|talk) to (a |an )?(person|someone))\b", re.I)
    TRUST = re.compile(r"trust|reliable|credib|more accurate|which (report|source)\b.{0,30}\b(better|best|accurate|reliable)|better (report|source)", re.I)
    COMPARE = re.compile(r"compare|comparison|versus|\bvs\b|difference|differ|disagree|conflict|\bboth\b", re.I)
    PRICING = re.compile(
        r"\bcheap(er|est)?\b.{0,40}\b(reports?|buy|purchase)\b|\b(reports?|buy|purchase)\b.{0,40}\bcheap(er|est)?\b|"
        r"\b(price|prices|pricing|cost|costs|fee|fees)\b.{0,25}\b(of|for|to (buy|get|access))\b.{0,20}\breports?\b|"
        r"\b(buy|purchase|subscribe to|license)\b.{0,30}\breports?\b|\breports?\b.{0,30}\b(price|pricing|cost|discount)\b|"
        r"how much (does|do|is|are)\b.{0,40}\b(reports?|subscription)\b",
        re.I,
    )
    THANKS = re.compile(r"^\s*(thanks?|thank you|thx|ty)\b.{0,40}$", re.I)
    MY_REPORTS = re.compile(
        r"\b(list|show|which|what)\b.{0,25}\breports?\b.{0,30}\b(i|we)\b.{0,15}\b(can|have|bought|purchased|own|access)\b|\bmy reports\b|\breports? (i|we) (have|can|bought|purchased|own|access)\b",
        re.I,
    )
    CALC = re.compile(r"calculate|compute|project|estimate", re.I)
    GREETING = re.compile(
        r"^\s*(hi+|hello+|hey+|heya|hola|yo|namaste|namaskar|good (morning|afternoon|evening)|thanks?( you)?|thx|ok(ay)?|cool|nice|great|help|menu|start|"
        r"what can you do|who are you|what are you|how are you|how can you help|what do you do|what can i (ask|do)( you| here)?( about)?|what should i ask|how (do|can) i use (you|this)|what do you know)[\s!.?,]*$",
        re.I,
    )

    def __init__(
        self,
        llm: LLMService,
        guard: InjectionGuard,
        parser: QuestionParser,
        planner: SqlPlanner,
        reports: ReportRepository,
        audit: AuditRepository,
        clients: ClientRepository,
        entitlement: EntitlementService,
    ) -> None:
        super().__init__(llm)
        self.guard = guard
        self.parser = parser
        self.planner = planner
        self.reports = reports
        self.audit = audit
        self.clients = clients
        self.entitlement = entitlement

    def __call__(self, state: dict) -> dict:
        question, client_id = state["question"], state["client_id"]
        reports = self.reports.all()
        parsed = self.parser.parse(question, reports)
        history = state.get("history", [])
        follow = False
        if FollowUp.applies(question, parsed, bool(history)):
            previous = None
            for earlier in history:
                current = self.parser.parse(earlier, reports)
                previous = FollowUp.overlay(previous, current) if previous and FollowUp.applies(earlier, current, True) else current
            parsed = FollowUp.overlay(previous, parsed)
            follow = True
        out = {"parsed": parsed, "flags": [], "refusal": None, "force_escalate": None}

        kinds = self.guard.classify_request(question)
        if kinds:
            refusal = "write_attempt" if "write_attempt" in kinds else kinds[0]
            self.audit.log_injection(client_id, refusal, "user_input", question)
            log_event(logger, "unsafe_request", client_id=client_id, kinds=kinds)
            flags = ["unsafe_request"] + (["write_blocked"] if refusal == "write_attempt" else [])
            return {**out, "intent": Intent.UNSAFE, "refusal": refusal, "flags": flags}

        entitled = self.entitlement.entitled_ids(client_id)
        out["entitled"] = entitled
        if self.THANKS.match(question):
            return {**out, "intent": Intent.GREETING, "note": "thanks"}
        if self.MY_REPORTS.search(question):
            return {**out, "intent": Intent.GREETING, "note": "my_reports"}
        if self.GREETING.match(question):
            return {**out, "intent": Intent.GREETING}
        if self.POLITICS.search(question):
            return {**out, "intent": Intent.OUT_OF_SCOPE, "refusal": "politics"}
        others = [c.company.lower() for c in self.clients.all() if c.id != client_id]
        if self.PRIVACY.search(question) or any(name in question.lower() for name in others):
            return {**out, "intent": Intent.OUT_OF_SCOPE, "refusal": "privacy"}
        if not parsed.report_ids and self.PRICING.search(question):
            return {**out, "intent": Intent.ESCALATE, "force_escalate": "pricing or purchase terms are not in the data", "note": "pricing"}
        if not self.DOMAIN.search(question) and not parsed.report_ids and not parsed.topic_ids and not follow:
            return {**out, "intent": Intent.OUT_OF_SCOPE, "refusal": "off_topic"}

        if self.ESCALATE.search(question):
            return {**out, "intent": Intent.ESCALATE, "force_escalate": "client asked for a human analyst"}
        if self.planner.looks_aggregate(question):
            return {**out, "intent": Intent.AGGREGATE}
        if self.TRUST.search(question):
            return {**out, "intent": Intent.TRUST}
        projection = "Market size" in parsed.metrics and parsed.year is not None and parsed.year > 2024
        regional_size = "Market size" in parsed.metrics and parsed.region == "APAC"
        if projection or regional_size or self.CALC.search(question):
            return {**out, "intent": Intent.CALCULATION}
        if self.COMPARE.search(question):
            return {**out, "intent": Intent.COMPARISON}
        return {**out, "intent": Intent.FACTUAL}
