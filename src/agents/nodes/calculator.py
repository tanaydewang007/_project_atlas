from src.agents.nodes.base import BaseNode
from src.services.calculator import CalculatorService
from src.services.llm import LLMService


class CalculatorNode(BaseNode):
    def __init__(self, llm: LLMService, calculator: CalculatorService) -> None:
        super().__init__(llm)
        self.calculator = calculator

    def __call__(self, state: dict) -> dict:
        parsed = state["parsed"]
        region = parsed.region or "Global"
        by_report: dict[str, dict] = {}
        for m in state.get("metrics", []):
            by_report.setdefault(m.report_id, {})[m.metric] = m
        base_years = [int(ms["Market size"].period) for ms in by_report.values() if "Market size" in ms]
        projecting = parsed.year is not None and bool(base_years) and parsed.year > max(base_years)

        derived, notes, used, exceeded = [], list(state.get("notes", [])), [], False
        for rid, ms in by_report.items():
            size, cagr, share = ms.get("Market size"), ms.get("CAGR"), ms.get("Regional share")
            if size is None:
                continue
            if projecting and cagr is not None:
                outcome = self.calculator.project_market(rid, size, cagr, share, region, parsed.year)
                derived += outcome.derived
                notes += outcome.notes
                exceeded = exceeded or outcome.window_exceeded
                if outcome.window_exceeded:
                    used.append(cagr)
                if outcome.derived:
                    used += [m for m in (size, cagr, share if region == "APAC" else None) if m]
            elif not projecting and region == "APAC" and share is not None:
                derived.append(self.calculator.regional_base(rid, size, share))
                used += [size, share]
            elif not projecting:
                used.append(size)

        force = state.get("force_escalate")
        if projecting and not derived:
            force = "requested year is outside every available forecast window" if exceeded else "no report has the inputs needed for this estimate"
        return {"derived": derived, "notes": notes, "used_metrics": used, "force_escalate": force}
