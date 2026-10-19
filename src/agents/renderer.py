import re

from src.models.domain import Intent, Metric, Report
from src.repositories.reports import ReportRepository


class AnswerRenderer:
    REFUSALS = {
        "prompt_override": "I can't help with that. I won't change my instructions or reveal internal data or any client's information. I can answer questions about the market research reports in your plan.",
        "data_exfiltration": "I can't help with that. I won't share client contact details or any other client's data. I can answer questions about the market research reports in your plan.",
        "write_attempt": "I can't do that. This assistant is read-only, so nothing was changed and no query was run. I can answer questions about the market research reports in your plan.",
        "privacy": "I can't share personal or confidential information such as contact details or other clients' purchases. I can help with the market research reports available to you.",
        "politics": "I can't help with political questions. I can help with market research topics, for example market size, growth forecasts, or which report best fits your needs.",
        "off_topic": "That is outside what I can help with. I answer questions about the market research reports in your plan, such as market size, forecasts and sources.",
    }

    def __init__(self, repo: ReportRepository) -> None:
        self.repo = repo
        self.reports: dict[str, Report] = {}

    def render(self, state: dict) -> str:
        self.reports = {r.id: r for r in self.repo.all()}
        if state.get("refusal") == "entitlement":
            return self._entitlement(state["blocked"])
        if state["intent"] == Intent.GREETING:
            return self._greeting(state)
        if state.get("refusal") in ("politics", "off_topic", "privacy"):
            return f"{self.REFUSALS[state['refusal']]}\n\n{self._help(state)}"
        if state.get("refusal"):
            return self.REFUSALS[state["refusal"]]
        intent = state["intent"]
        if intent == Intent.ESCALATE:
            if state.get("note") == "pricing":
                return "I don't have pricing or purchase terms for the reports, so I can't say which one is cheaper. I'll pass your question to a human analyst who can check with your account team."
            return "I'll hand your question to a human analyst."
        if intent == Intent.AGGREGATE:
            return self._aggregate(state)
        if intent == Intent.TRUST:
            body = self._trust(state)
        elif intent == Intent.CALCULATION:
            body = self._calculation(state)
        else:
            body = self._lookup(state)
        extra = [self._locked_note(state["locked"])] if state.get("locked") else []
        return "\n\n".join([body] + extra)

    def _topics(self, state: dict) -> list[tuple[Report, str]]:
        entitled = [self.reports[i] for i in state.get("entitled", []) if i in self.reports]
        topics = []
        for report in entitled:
            words = [w for w in re.sub(r"\b(19|20)\d{2}\b|[:,]", " ", report.title).split() if w.lower() not in {"global", "market", "industry", "outlook", "report"}]
            if words:
                topics.append((report, " ".join(words).lower()))
        return topics

    def _help(self, state: dict) -> str:
        topics = self._topics(state)
        if not topics:
            return "You don't have any reports in your plan yet, so there is nothing I can answer from."
        lines = ["For example, you could ask:"]
        for report, topic in topics[:2]:
            lines.append(f"- What was the global {topic} market size in 2024?")
        lines.append("- Which report should I trust?")
        return "\n".join(lines)

    def _greeting(self, state: dict) -> str:
        entitled = [self.reports[i] for i in state.get("entitled", []) if i in self.reports]
        if state.get("note") == "thanks":
            return "You're welcome! Ask me anything else about your reports.\n\n" + self._help(state)
        if state.get("note") == "my_reports":
            lines = ["Here are the reports in your plan:"] + [f"- {r.id}: {r.title} ({r.publisher})" for r in entitled]
            return "\n".join(lines + ["", self._help(state)]) if entitled else self._help(state)
        lines = ["Hi! I'm the Report Copilot. I answer questions from the market research reports in your plan, and I show where every number comes from."]
        if entitled:
            lines += ["", "Reports you can ask about:"] + [f"- {r.id}: {r.title} ({r.publisher})" for r in entitled]
        lines += ["", self._help(state), "", "If sources disagree I show both, I label any estimate I calculate, and when I'm not sure I pass your question to a human analyst."]
        return "\n".join(lines)

    def _entitlement(self, blocked: list[Report]) -> str:
        names = "; ".join(f"{r.id} ({r.title}, {r.publisher})" for r in blocked)
        return (
            f"{names} exists in our library but is not part of your plan, so I can't share its contents or figures. "
            "To get access, ask your CMR account manager for an upgrade and I can answer questions about it afterwards."
        )

    def _locked_note(self, locked: list[Report]) -> str:
        names = "; ".join(sorted({f"{r.id} ({r.title})" for r in locked}))
        return f"Note: further CMR report(s) on this topic exist but are not part of your plan, so I haven't used them: {names}. They can be added through an upgrade."

    def _line(self, m: Metric) -> str:
        r = self.reports[m.report_id]
        return f"- {m.report_id} ({r.title}, {r.publisher}): {m.metric} {m.region} {m.period} = {m.display}. Scope: {m.scope_note}. (p.{m.page})"

    def _lookup(self, state: dict) -> str:
        metrics, notes = state.get("used_metrics", []), state.get("notes", [])
        lines: list[str] = []
        if metrics:
            if state.get("ambiguous_topic") and len({self.reports[m.report_id].sector for m in metrics}) > 1:
                lines.append("Your question didn't name a market, so here is every market in your plan:")
            else:
                lines.append("Here is what the reports available to you say:")
            lines += [self._line(m) for m in metrics]
            for c in state.get("conflicts", []):
                lines.append(f"\nSources disagree on {c.topic}:")
                lines += [f"- {v.report_id}: {v.value}. Scope: {v.scope_note}" for v in c.values]
                lines.append(c.explanation)
        elif notes:
            lines.append("I can't find a published figure that matches that request.")
        elif state.get("chunks"):
            lines.append("I don't have a quoted figure for that. These passages from your reports are relevant:")
            lines += [f"- {c.text[:300]} ({c.report_id}, p.{c.page})" for c in state["chunks"][:3]]
        else:
            lines.append("I couldn't find anything in the reports available to you that answers this.")
        return "\n".join(lines + notes)

    def _calculation(self, state: dict) -> str:
        derived, notes = state.get("derived", []), state.get("notes", [])
        if not derived:
            if state.get("used_metrics") and not state.get("force_escalate"):
                return self._lookup(state)
            return "\n".join(["I can't give a figure for that, and I won't extrapolate beyond what the reports support."] + notes)
        lines = ["These are derived estimates (calculated, not figures quoted from a report):"]
        for d in derived:
            lines += [f"- {d.label}: {d.value}", f"  Formula: {d.formula}", f"  Assumptions: {'; '.join(d.assumptions)}"]
        return "\n".join(lines + notes)

    def _aggregate(self, state: dict) -> str:
        result = state.get("sql_result")
        if result is None:
            return f"I couldn't run a safe query for that question ({state.get('sql_error', 'unknown error')})."
        rows = [", ".join(f"{c}={v}" for c, v in zip(result.columns, row)) for row in result.rows[:10]]
        suffix = ["(more rows not shown)"] if result.truncated or len(result.rows) > 10 else []
        return "\n".join([f"Query used: {result.query}", "Result (ordered as returned):"] + [f"- {r}" for r in rows] + suffix)

    def _trust(self, state: dict) -> str:
        metrics = state.get("used_metrics", [])
        if not metrics:
            return "None of the topics in your plan are covered by more than one report, so there is no disagreement to resolve; each report is the only source for its topic."
        lines = ["There is no single report that is simply more correct; which to trust depends on what you need."]
        for m in metrics:
            r = self.reports[m.report_id]
            source = "independent third party" if "third party" in r.publisher else "CMR"
            lines.append(f"- {m.report_id} ({r.title}): {m.display} for {m.period}, published {r.published}, source: {source}, access: {r.access}. Scope: {m.scope_note}. (p.{m.page})")
        if len(metrics) >= 2:
            narrow = [m for m in metrics if "only" in m.scope_note.lower()]
            broad = [m for m in metrics if m not in narrow]
            if narrow and broad:
                lines.append(f"If you need total market spend, lean on {broad[0].report_id} (broader scope). If you only need device spend, use {narrow[0].report_id}. The figures are not interchangeable and should not be averaged.")
            newest = max(metrics, key=lambda m: self.reports[m.report_id].published)
            lines.append(f"{newest.report_id} is the most recent of these.")
        else:
            lines.append("Within your plan I can only see one of the reports on this topic, so I can't compare it against the others.")
        lines.append("I can't independently verify which methodology is more accurate, so my confidence is moderate. If this matters for a procurement decision, ask me to escalate to a human analyst.")
        return "\n".join(lines)
