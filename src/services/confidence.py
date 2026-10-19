from src.models.domain import Intent


class ConfidenceScorer:
    def score(self, state: dict) -> float:
        intent = state["intent"]
        if state.get("refusal") or intent in (Intent.UNSAFE, Intent.OUT_OF_SCOPE, Intent.GREETING):
            base = 0.95
        elif intent == Intent.ESCALATE:
            base = 0.3
        elif intent == Intent.AGGREGATE:
            base = 0.9 if state.get("sql_result") else 0.2
        elif intent == Intent.CALCULATION:
            derived = state.get("derived", [])
            base = 0.2 if not derived else 0.65 if len({d.source_reports[0] for d in derived}) < len(derived) else 0.7
        elif intent == Intent.TRUST:
            accessible = len(state.get("used_metrics", []))
            base = 0.7 if accessible == 0 and not state.get("locked") else 0.6 if accessible >= 2 else 0.5
        elif state.get("used_metrics"):
            base = 0.85 - (0.05 if state.get("conflicts") else 0) - (0.2 if state.get("ambiguous_topic") else 0)
        elif state.get("chunks"):
            base = min(0.75, 0.25 + 0.6 * max(c.score for c in state["chunks"]))
        else:
            base = 0.1
        return round(max(0.0, min(1.0, base * state.get("verified_ratio", 1.0))), 2)
