import logging
import math
import re
from collections import defaultdict

from src.agents.nodes.base import BaseNode
from src.core.errors import SqlRejected
from src.core.logging import log_event
from src.models.domain import Intent, Metric
from src.repositories.audit import AuditRepository
from src.repositories.reports import ReportRepository
from src.services.conflicts import ConflictService
from src.services.entitlement import EntitlementService
from src.services.injection_guard import InjectionGuard
from src.services.llm import LLMService
from src.services.question_parser import stems
from src.services.sql_planner import SqlPlanner
from src.services.sql_tool import SqlToolService
from src.services.vector_store import VectorStore
from src.core.config import Settings

logger = logging.getLogger(__name__)

SYNONYMS = {"chall": {"restr", "barri", "risk"}, "obsta": {"restr", "barri"}, "hurdl": {"restr"}, "probl": {"restr", "risk"}, "benef": {"drive", "driv"}}


class RetrieverNode(BaseNode):
    def __init__(
        self,
        llm: LLMService,
        settings: Settings,
        entitlement: EntitlementService,
        reports: ReportRepository,
        store: VectorStore,
        sql_tool: SqlToolService,
        planner: SqlPlanner,
        guard: InjectionGuard,
        audit: AuditRepository,
    ) -> None:
        super().__init__(llm)
        self.settings = settings
        self.entitlement = entitlement
        self.reports = reports
        self.store = store
        self.sql_tool = sql_tool
        self.planner = planner
        self.guard = guard
        self.audit = audit

    def __call__(self, state: dict) -> dict:
        client_id, question, intent, parsed = state["client_id"], state["question"], state["intent"], state["parsed"]
        entitled = self.entitlement.entitled_ids(client_id)
        by_id = {r.id: r for r in self.reports.all()}
        out: dict = {"entitled": entitled, "flags": list(state["flags"])}

        if intent == Intent.AGGREGATE:
            return {**out, **self._aggregate(state)}
        if intent == Intent.TRUST:
            return {**out, **self._trust(state, entitled, by_id)}

        requested = [i for i in parsed.report_ids if i in entitled]
        blocked = [by_id[i] for i in parsed.report_ids if i in by_id and i not in entitled]
        locked_topic = [by_id[i] for i in parsed.topic_ids if i not in entitled]
        candidates = requested or [i for i in parsed.topic_ids if i in entitled]
        ambiguous = not (requested or parsed.topic_ids)
        if ambiguous and parsed.metrics and parsed.unknown >= 2:
            return {
                **out,
                "candidates": [],
                "metrics": [],
                "chunks": [],
                "used_metrics": [],
                "locked": [],
                "ambiguous_topic": False,
                "notes": ["None of the reports in your plan cover that topic."],
                "force_escalate": "the topic is not covered by any report in the plan",
            }
        if ambiguous:
            candidates = entitled
        locked = blocked + locked_topic

        if not candidates or (blocked and not requested):
            if locked:
                return {**out, "refusal": "entitlement", "blocked": locked, "flags": out["flags"] + ["entitlement_denied"]}
            return {**out, "candidates": [], "metrics": [], "chunks": [], "used_metrics": [], "locked": [], "ambiguous_topic": False}

        metrics = self.reports.metrics(candidates)
        notes: list[str] = []
        if parsed.other_region:
            notes.append(f"The reports available to you contain no {parsed.other_region} breakdown.")
            metrics = []
        elif intent != Intent.CALCULATION:
            metrics = self._select(metrics, parsed, notes)
        force = "no published figure matches the request" if notes and not metrics else None
        conflicts = ConflictService(by_id).detect(metrics) if intent != Intent.CALCULATION else []
        chunks, flags = self._chunks(state, question, candidates)
        return {
            **out,
            "flags": out["flags"] + flags,
            "candidates": candidates,
            "ambiguous_topic": ambiguous,
            "locked": locked,
            "metrics": metrics,
            "used_metrics": metrics if intent != Intent.CALCULATION else [],
            "conflicts": conflicts,
            "chunks": chunks,
            "notes": notes,
            "force_escalate": force,
        }

    @staticmethod
    def _select(metrics: list[Metric], parsed, notes: list[str]) -> list[Metric]:
        if not parsed.metrics:
            return []
        selected = [m for m in metrics if m.metric in parsed.metrics]
        sizes = [int(m.period) for m in metrics if m.metric == "Market size"]
        if parsed.year and sizes and parsed.year <= max(sizes):
            matching = [m for m in selected if m.metric == "CAGR" or m.period == str(parsed.year)]
            if not any(m.metric != "CAGR" for m in matching) and any(m.metric != "CAGR" for m in selected):
                notes.append(f"No figure is published for {parsed.year}; the reports cover {max(sizes)}.")
            selected = matching
        return selected

    def _chunks(self, state: dict, question: str, scope: list[str]) -> tuple[list, list[str]]:
        titles = {r.id: r.title for r in self.reports.all()}
        topic = set().union(*(stems(titles.get(r, "")) for r in scope)) if len(scope) < len(titles) else set()
        wanted = stems(question) - topic
        wanted |= {s for w in list(wanted) for s in SYNONYMS.get(w, ())}
        found = self.store.search(question, scope, self.settings.retrieval_top_k * 3)
        chunk_stems = [stems(c.text) for c in found]
        idf = {w: math.log(1 + len(found) / max(1, sum(w in s for s in chunk_stems))) for w in wanted}
        total = sum(idf.values()) or 1.0
        for chunk, present in zip(found, chunk_stems):
            chunk.score = 0.5 * chunk.score + 0.5 * sum(idf[w] for w in wanted & present) / total
        found = sorted(found, key=lambda c: c.score, reverse=True)[: self.settings.retrieval_top_k]
        kept, flags = [], []
        for chunk in found:
            clean, hits = self.guard.sanitize(chunk.text)
            for hit in hits:
                self.audit.log_injection(state["client_id"], "document_injection", f"{chunk.report_id} p.{chunk.page}", hit)
                log_event(logger, "injection_detected", client_id=state["client_id"], source=f"{chunk.report_id} p.{chunk.page}")
                if "injection_detected" not in flags:
                    flags.append("injection_detected")
            chunk.text = clean
            if clean and chunk.score >= self.settings.retrieval_min_score:
                kept.append(chunk)
        return kept, flags

    def _aggregate(self, state: dict) -> dict:
        question = state["question"]
        sql = self.planner.template(question)
        if sql is None:
            raw = self.ask_llm(state, self.planner.SYSTEM, question)
            sql = re.sub(r"^```(?:sql)?|```$", "", raw or "", flags=re.M).strip() or None
        if sql is None:
            return {"sql_error": "no safe query could be generated", "sql_queries": []}
        try:
            result = self.sql_tool.run(state["client_id"], sql)
        except SqlRejected as exc:
            return {"sql_error": str(exc), "sql_queries": [sql]}
        return {"sql_result": result, "sql_queries": [result.query]}

    def _trust(self, state: dict, entitled: list[str], by_id: dict) -> dict:
        parsed = state["parsed"]
        sizes = [m for m in self.reports.metrics() if m.metric == "Market size"]
        if parsed.topic_ids:
            sizes = [m for m in sizes if m.report_id in parsed.topic_ids]
        groups: dict[tuple, list[Metric]] = defaultdict(list)
        for m in sizes:
            groups[(by_id[m.report_id].sector, m.region, m.period)].append(m)
        multi = [g for g in groups.values() if len(g) > 1 and any(m.report_id in entitled for m in g)]
        accessible = [m for g in multi for m in g if m.report_id in entitled]
        locked = [by_id[m.report_id] for g in multi for m in g if m.report_id not in entitled]
        chunks, flags = self._chunks(state, state["question"], [m.report_id for m in accessible]) if accessible else ([], [])
        return {
            "flags": state["flags"] + flags,
            "metrics": accessible,
            "used_metrics": accessible,
            "locked": locked,
            "chunks": chunks,
            "conflicts": ConflictService(by_id).detect(accessible),
            "ambiguous_topic": False,
        }
