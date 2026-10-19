from collections import defaultdict

from src.models.domain import Metric, Report
from src.models.schemas import Conflict, ConflictValue


class ConflictService:
    def __init__(self, reports: dict[str, Report]) -> None:
        self.reports = reports

    def _key(self, m: Metric) -> tuple:
        sector = self.reports[m.report_id].sector
        return (sector, m.metric, m.region) if m.metric == "CAGR" else (sector, m.metric, m.region, m.period)

    def detect(self, metrics: list[Metric]) -> list[Conflict]:
        groups: dict[tuple, list[Metric]] = defaultdict(list)
        for m in metrics:
            groups[self._key(m)].append(m)
        conflicts = []
        for key, members in groups.items():
            if len({m.report_id for m in members}) < 2 or len({m.value for m in members}) < 2:
                continue
            values = [
                ConflictValue(
                    report_id=m.report_id,
                    title=self.reports[m.report_id].title,
                    value=m.display,
                    scope_note=m.scope_note + (f" (window {m.period})" if m.metric == "CAGR" else ""),
                )
                for m in members
            ]
            conflicts.append(
                Conflict(
                    topic=f"{key[2]} {key[1].lower()} ({key[0]})" + (f" {key[3]}" if len(key) > 3 else ""),
                    values=values,
                    explanation="The reports give different figures for the same measure because their scope or window differs. Both are shown and neither is averaged or preferred silently.",
                )
            )
        return conflicts
