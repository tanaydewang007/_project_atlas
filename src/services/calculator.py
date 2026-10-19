from dataclasses import dataclass, field

from src.models.domain import Metric
from src.models.schemas import DerivedValue


@dataclass
class ProjectionOutcome:
    derived: list[DerivedValue] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    window_exceeded: bool = False


class CalculatorService:
    @staticmethod
    def project(base: float, rate_pct: float, periods: int) -> float:
        return base * (1 + rate_pct / 100) ** periods

    def regional_base(self, report_id: str, size: Metric, share: Metric) -> DerivedValue:
        value = size.value * share.value / 100
        return DerivedValue(
            label=f"{report_id} APAC market size {size.period} (derived)",
            value=f"USD {value:.2f} B",
            formula=f"{size.value:g} x {share.value / 100:g} = {value:.2f}",
            assumptions=[f"APAC share ({share.display}) applied to the global market size", f"Scope: {size.scope_note}"],
            inputs={"global_market_size": size.display, "apac_share": share.display},
            source_reports=[report_id],
        )

    def project_market(self, report_id: str, size: Metric, cagr: Metric, share: Metric | None, region: str, target_year: int) -> ProjectionOutcome:
        start, end = (int(x) for x in cagr.period.split("-"))
        base_year = int(size.period)
        if target_year > end:
            return ProjectionOutcome(
                notes=[f"{report_id}: its forecast window ends in {end}, so I did not extrapolate to {target_year}."],
                window_exceeded=True,
            )
        if region == "APAC" and share is None:
            return ProjectionOutcome(notes=[f"{report_id}: no APAC share is available, so no regional estimate was computed."])
        options = {target_year - base_year: f"compounding from the {base_year} base year"}
        options.setdefault(target_year - start, f"treating the {base_year} figure as the starting value of the {start}-{end} CAGR window")
        outcome = ProjectionOutcome()
        for n, (periods, why) in enumerate(sorted(options.items(), reverse=True)):
            value = self.project(size.value, cagr.value, periods)
            formula = f"{size.value:g} x (1 + {cagr.value / 100:g})^{periods} = {value:.2f}"
            assumptions = [
                f"CAGR of {cagr.display} applied uniformly each year",
                f"{periods} growth periods, {why}",
                f"Scope: {size.scope_note}",
            ]
            inputs = {"base_value": f"{size.display} ({size.period})", "cagr": f"{cagr.display} ({cagr.period})", "periods": str(periods)}
            if region == "APAC":
                value *= share.value / 100
                formula += f"; APAC = {value / (share.value / 100):.2f} x {share.value / 100:g} = {value:.2f}"
                assumptions.append(f"APAC share held constant at the {share.period} level of {share.display}")
                inputs["apac_share"] = share.display
            label = f"{report_id} {region} market size {target_year}" + (f" (variant {'AB'[n]})" if len(options) > 1 else "")
            outcome.derived.append(
                DerivedValue(label=label, value=f"USD {value:.2f} B", formula=formula, assumptions=assumptions, inputs=inputs, source_reports=[report_id])
            )
        if len(options) > 1:
            outcome.notes.append(
                f"{report_id}: the market size is for {base_year} but the CAGR window starts in {start}, so the base year is ambiguous; both readings are shown."
            )
        return outcome
