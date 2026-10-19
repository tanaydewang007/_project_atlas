from src.tests.conftest import ADMIN, C01, ask


def test_new_report_is_usable_without_restart(client, container, tmp_path):
    (tmp_path / "R-107.md").write_text(
        "[[page 1]]\n## Summary\nThe global smart grid analytics market was valued at USD 5.5 billion in 2024 "
        "and is expected to grow at a CAGR of 8.0% from 2025 to 2030.\n"
    )
    with container.db.connect() as conn:
        conn.execute("INSERT INTO reports VALUES ('R-107','Smart Grid Analytics Market 2025','CMR','2025-05-01','Energy','paid')")
        conn.execute(
            "INSERT INTO market_metrics (report, metric, region, period, value, unit, scope_note, page) "
            "VALUES ('R-107','Market size','Global','2024',5.5,'USD B','Software and services',1)"
        )
        conn.execute("UPDATE clients SET purchased_reports = purchased_reports || ', R-107' WHERE id = 'C-01'")
    container.ingestion.dir = tmp_path
    body = client.post("/ingest", json={"report_ids": ["R-107"]}, headers=ADMIN).json()
    assert body["reports_ingested"] == ["R-107"]
    r = ask(client, "C-01", "What is the smart grid analytics market size in 2024?", C01)
    assert "5.5" in r["answer"] and [c["report_id"] for c in r["citations"]] == ["R-107"]
    with container.db.connect() as conn:
        conn.execute("DELETE FROM market_metrics WHERE report = 'R-107'")
        conn.execute("DELETE FROM reports WHERE id = 'R-107'")
        conn.execute("UPDATE clients SET purchased_reports = REPLACE(purchased_reports, ', R-107', '') WHERE id = 'C-01'")
    container.store.delete_report("R-107")
