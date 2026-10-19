import pytest

from src.core.errors import SqlRejected


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM reports",
        "DROP TABLE reports",
        "SELECT 1; DELETE FROM reports",
        "PRAGMA table_info(reports)",
        "UPDATE reports SET title='x'",
        "INSERT INTO reports VALUES (1)",
        "ATTACH DATABASE 'x.db' AS x",
        "SELECT * FROM sqlite_master",
    ],
)
def test_writes_and_escapes_are_rejected(container, sql):
    with pytest.raises(SqlRejected):
        container.sql_tool.run("C-01", sql)


def test_clients_table_is_unreachable(container):
    with pytest.raises(SqlRejected):
        container.sql_tool.run("C-01", "SELECT contact_email FROM clients")


def test_metrics_are_filtered_by_entitlement(container):
    rows = container.sql_tool.run("C-02", "SELECT DISTINCT report FROM market_metrics ORDER BY report").rows
    assert [r[0] for r in rows] == ["R-102", "R-103"]
    rows = container.sql_tool.run("C-01", "SELECT DISTINCT report FROM market_metrics ORDER BY report").rows
    assert [r[0] for r in rows] == ["R-101", "R-102", "R-103"]


def test_row_limit_truncates(container):
    result = container.sql_tool.run("C-01", "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c LIMIT 500) SELECT x FROM c")
    assert result.truncated and len(result.rows) == container.settings.sql_row_limit


def test_runaway_query_times_out(container):
    with pytest.raises(SqlRejected):
        container.sql_tool.run("C-01", "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT COUNT(*) FROM c")


def test_database_is_untouched(container):
    assert len(container.reports.all()) == 6
