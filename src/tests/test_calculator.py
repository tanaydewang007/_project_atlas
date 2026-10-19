from src.models.domain import Metric
from src.services.calculator import CalculatorService

SIZE = Metric("R-101", "Market size", "Global", "2024", 4.21, "USD B", "all", 8)
CAGR = Metric("R-101", "CAGR", "Global", "2025-2030", 11.2, "%", "window", 8)
SHARE = Metric("R-101", "Regional share", "APAC", "2024", 38.0, "%", "share", 8)


def test_both_base_year_readings_are_returned():
    out = CalculatorService().project_market("R-101", SIZE, CAGR, SHARE, "APAC", 2030)
    assert [d.value for d in out.derived] == ["USD 3.02 B", "USD 2.72 B"]
    assert any("ambiguous" in n for n in out.notes)


def test_global_projection():
    out = CalculatorService().project_market("R-101", SIZE, CAGR, None, "Global", 2030)
    assert [d.value for d in out.derived] == ["USD 7.96 B", "USD 7.16 B"]


def test_no_extrapolation_beyond_window():
    out = CalculatorService().project_market("R-101", SIZE, CAGR, SHARE, "Global", 2035)
    assert out.window_exceeded and not out.derived


def test_formula_is_exposed():
    out = CalculatorService().project_market("R-101", SIZE, CAGR, None, "Global", 2030)
    assert "(1 + 0.112)^6" in out.derived[0].formula
