from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    client_id: str
    question: str
    history: list[str]
    note: str | None
    meter: Any
    intent: Any
    parsed: Any
    refusal: str | None
    flags: list[str]
    entitled: list[str]
    blocked: list[Any]
    locked: list[Any]
    candidates: list[str]
    ambiguous_topic: bool
    metrics: list[Any]
    used_metrics: list[Any]
    chunks: list[Any]
    sql_result: Any
    sql_error: str | None
    sql_queries: list[str]
    conflicts: list[Any]
    derived: list[Any]
    notes: list[str]
    force_escalate: str | None
    draft: str
    used_llm: bool
    deterministic: bool
    citations: list[Any]
    critic_ok: bool
    critic_issues: list[str]
    verified_ratio: float
    confidence: float
    answer: str
    escalated: bool
    escalation_id: int | None
