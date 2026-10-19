import re

from src.agents.nodes.base import BaseNode
from src.services.confidence import ConfidenceScorer
from src.services.llm import LLMService

NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")
CITE_TAG = re.compile(r"(R-\d+),\s*p\.\s?(\d+)")
STRIP = re.compile(r"R-\d+|\bp\.\s?\d+|\d{4}-\d{2}-\d{2}|#\d+")


def numbers(text: str) -> set[float]:
    found = set()
    for token in NUMBER.findall(STRIP.sub(" ", text)):
        value = float(token)
        if "." not in token and 1900 <= value <= 2100:
            continue
        found.add(round(value, 4))
    return found


class CriticNode(BaseNode):
    def __init__(self, llm: LLMService, scorer: ConfidenceScorer) -> None:
        super().__init__(llm)
        self.scorer = scorer

    def __call__(self, state: dict) -> dict:
        draft = state["draft"]
        grounded = numbers(state["question"])
        for c in state.get("citations", []):
            grounded |= numbers(c.snippet)
        for d in state.get("derived", []):
            grounded |= numbers(" ".join([d.value, d.formula, *d.assumptions, *d.inputs.values()]))
        result = state.get("sql_result")
        if result is not None:
            grounded |= numbers(result.query) | numbers(" ".join(str(v) for row in result.rows for v in row))

        found = numbers(draft)
        unverified = sorted(found - grounded)
        issues = [f"number {n:g} has no supporting citation" for n in unverified]
        for conflict in state.get("conflicts", []):
            for v in conflict.values:
                if not numbers(v.value) <= numbers(draft):
                    issues.append(f"conflict value {v.value} from {v.report_id} is missing from the draft")
        cited = {(c.report_id, str(c.page)) for c in state.get("citations", [])}
        issues += [f"citation {rid}, p.{page} does not match any source" for rid, page in sorted(set(CITE_TAG.findall(draft)) - cited)]
        if result is None and "Query used:" in draft:
            issues.append("the draft mentions a SQL query that was never run")
        if result is not None and result.query not in draft:
            issues.append("the SQL query used is missing from the draft")
        for d in state.get("derived", []):
            if not numbers(d.value) <= found:
                issues.append(f"derived value {d.value} is missing from the draft")
        ratio = (len(found) - len(unverified)) / len(found) if found else 1.0
        retry = bool(issues) and state.get("used_llm", False)
        verified = {"verified_ratio": 1.0 if retry else ratio}
        confidence = self.scorer.score({**state, **verified})
        return {
            "critic_ok": not issues,
            "critic_issues": issues,
            "deterministic": retry or state.get("deterministic", False),
            **verified,
            "confidence": confidence,
        }
