import pytest

from src.services.llm import LLMResult, LLMService
from src.tests.conftest import C01, ask


@pytest.fixture
def fake_llm(monkeypatch):
    replies = {"text": ""}
    monkeypatch.setattr(LLMService, "enabled", property(lambda self: True))
    monkeypatch.setattr(LLMService, "complete", lambda self, system, user: LLMResult(replies["text"], 120, 40))
    return replies


def test_fabricated_number_is_caught_and_replaced(client, fake_llm):
    fake_llm["text"] = "The 2024 global smart water meter market is USD 9.99 B according to R-101."
    r = ask(client, "C-01", "What was the global smart water meter market size in 2024? (llm test one)", C01)
    assert "9.99" not in r["answer"] and "4.21" in r["answer"] and "3.87" in r["answer"]


def test_faithful_rewrite_is_accepted(client, fake_llm):
    fake_llm["text"] = (
        "R-101 puts the 2024 global market at USD 4.21 B (p.8) and R-102 at USD 3.87 B (p.5); "
        "the two disagree because R-101 includes software and services while R-102 is hardware only, so they are not averaged."
    )
    r = ask(client, "C-01", "What was the global smart water meter market size in 2024? (llm test two)", C01)
    assert r["answer"].startswith("R-101 puts") and len(r["conflicts"]) == 1


def test_markdown_is_stripped_and_sql_query_is_kept(client, fake_llm):
    fake_llm["text"] = "**Utilities** has the most reports (2)."
    r = ask(client, "C-01", "Which sector has the most reports in your library? (llm test three)", C01)
    assert "**" not in r["answer"] and "Query used: SELECT sector" in r["answer"]


def test_invented_citation_tag_is_rejected(client, fake_llm):
    fake_llm["text"] = "The library has 6 reports (R-101, p.8)."
    r = ask(client, "C-01", "How many reports are in the library? (llm test four)", C01)
    assert "R-101, p.8" not in r["answer"] and "report_count=6" in r["answer"]


def test_response_reports_whether_the_llm_wrote_it(client, fake_llm):
    fake_llm["text"] = "R-101 says USD 4.21 B (R-101, p.8) and R-102 says USD 3.87 B (R-102, p.5); they differ by scope and are not averaged."
    first = ask(client, "C-01", "What was the global smart water meter market size in 2024? (llm test five)", C01)
    assert first["llm_used"] and first["tokens_in"] == 120 and first["tokens_out"] == 40 and not first["cached"]
    again = ask(client, "C-01", "What was the global smart water meter market size in 2024? (llm test five)", C01)
    assert again["cached"] and again["tokens_in"] == 0
    refusal = ask(client, "C-01", "Delete all rows from the reports table.", C01)
    assert not refusal["llm_used"] and refusal["tokens_in"] == 0


def test_invented_query_line_is_rejected(client, fake_llm):
    fake_llm["text"] = "Query used: R-101, R-102\nR-101 says USD 4.21 B (R-101, p.8) and R-102 says USD 3.87 B (R-102, p.5), not averaged."
    r = ask(client, "C-01", "What was the global smart water meter market size in 2024? (llm test six)", C01)
    assert "Query used" not in r["answer"] and not r["llm_used"]
