import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ChatRequest(BaseModel):
    client_id: str = Field(pattern=r"^C-\d{2,4}$")
    message: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = Field(default=None, max_length=64)

    @field_validator("message")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be blank")
        return value


class Citation(BaseModel):
    report_id: str | None
    title: str
    page: int | None = None
    snippet: str


class ConflictValue(BaseModel):
    report_id: str
    title: str
    value: str
    scope_note: str


class Conflict(BaseModel):
    topic: str
    values: list[ConflictValue]
    explanation: str


class DerivedValue(BaseModel):
    label: str
    value: str
    formula: str
    assumptions: list[str]
    inputs: dict[str, str]
    source_reports: list[str]


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: float
    conflicts: list[Conflict]
    derived_values: list[DerivedValue]
    escalated: bool
    escalation_id: int | None = None
    intent: str
    flags: list[str] = []
    sql_queries: list[str] = []
    conversation_id: str
    message_id: int
    llm_used: bool = False
    tokens_in: int = 0
    tokens_out: int = 0
    cached: bool = False


class IngestRequest(BaseModel):
    report_ids: list[str] | None = None


class IngestResult(BaseModel):
    reports_ingested: list[str]
    chunks: int
    skipped: dict[str, str]


class EscalationOut(BaseModel):
    id: int
    client_id: str
    question: str
    reason: str
    confidence: float
    status: str
    created_at: str


class FeedbackRequest(BaseModel):
    message_id: int
    rating: Literal["up", "down"]
    comment: str | None = Field(default=None, max_length=500)


class MetricIn(BaseModel):
    metric: Literal["Market size", "CAGR", "Regional share"]
    region: str = Field(min_length=1, max_length=30)
    period: str
    value: float = Field(gt=0, lt=1_000_000)
    scope_note: str = Field(default="", max_length=200)
    page: int | None = Field(default=None, ge=1, le=10_000)

    @model_validator(mode="after")
    def check_period(self) -> "MetricIn":
        if self.metric == "CAGR":
            if not re.fullmatch(r"\d{4}-\d{4}", self.period) or int(self.period[5:]) <= int(self.period[:4]):
                raise ValueError("CAGR period must look like 2025-2030")
        elif not re.fullmatch(r"\d{4}", self.period):
            raise ValueError(f"{self.metric} period must be a single year like 2024")
        if self.metric == "Regional share" and self.value > 100:
            raise ValueError("share must be at most 100")
        return self

    @property
    def unit(self) -> str:
        return "USD B" if self.metric == "Market size" else "%"


class ReportCreate(BaseModel):
    id: str | None = Field(default=None, pattern=r"^R-\d{3,4}$")
    title: str = Field(min_length=3, max_length=200)
    publisher: str = Field(min_length=1, max_length=100)
    published: str
    sector: str = Field(min_length=1, max_length=60)
    access: Literal["paid", "public excerpt"] = "paid"
    client_ids: list[str] = []
    metrics: list[MetricIn] = []

    @field_validator("published")
    @classmethod
    def iso_date(cls, value: str) -> str:
        date.fromisoformat(value)
        return value


class MetricOut(BaseModel):
    metric: str
    region: str
    period: str
    value: float
    unit: str
    scope_note: str
    page: int | None


class ReportAdminOut(BaseModel):
    id: str
    title: str
    publisher: str
    published: str
    sector: str
    access: str
    chunks: int
    source_file: str | None
    client_ids: list[str]
    metrics: list[MetricOut]


class ChunkOut(BaseModel):
    id: str
    page: int
    text: str
    suspicious: bool


class ClientBrief(BaseModel):
    id: str
    company: str


class AdminOverview(BaseModel):
    reports: list[ReportAdminOut]
    clients: list[ClientBrief]


class AccessUpdate(BaseModel):
    client_ids: list[str]
