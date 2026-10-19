from dataclasses import dataclass, field
from enum import Enum


class Intent(str, Enum):
    FACTUAL = "factual"
    COMPARISON = "comparison"
    CALCULATION = "calculation"
    AGGREGATE = "aggregate"
    TRUST = "trust"
    ESCALATE = "escalate_request"
    GREETING = "greeting"
    OUT_OF_SCOPE = "out_of_scope"
    UNSAFE = "unsafe"


@dataclass(frozen=True)
class Report:
    id: str
    title: str
    publisher: str
    published: str
    sector: str
    access: str

    @property
    def is_public(self) -> bool:
        return self.access != "paid"


@dataclass(frozen=True)
class Metric:
    report_id: str
    metric: str
    region: str
    period: str
    value: float
    unit: str
    scope_note: str
    page: int | None

    @property
    def display(self) -> str:
        if self.unit == "%":
            return f"{self.value:g}%"
        return f"USD {self.value:g} B"


@dataclass(frozen=True)
class Client:
    id: str
    company: str
    contact_email: str
    purchased: tuple[str, ...]


@dataclass
class Chunk:
    id: str
    report_id: str
    page: int
    text: str
    score: float = 0.0


@dataclass
class ParsedQuestion:
    report_ids: list[str] = field(default_factory=list)
    topic_ids: list[str] = field(default_factory=list)
    metric: str | None = None
    region: str | None = None
    year: int | None = None
    other_region: str | None = None
    metrics: list[str] = field(default_factory=list)
    unknown: int = 0
