from sre_toolkit.cost import (
    CostRecord,
    by_service,
    mom_change,
    month_totals,
    over_budget,
    records_from_json,
    to_markdown,
    top_spenders,
    total,
)


def _records() -> list:
    return [
        CostRecord("api", 400, "2026-10"),
        CostRecord("api", 100, "2026-09"),
        CostRecord("db", 300, "2026-10"),
        CostRecord("db", 300, "2026-09"),
        CostRecord("cache", 100, "2026-10"),
    ]


def test_total():
    assert total(_records()) == 1200


def test_by_service_sorted_desc():
    assert by_service(_records()) == [("db", 600), ("api", 500), ("cache", 100)]


def test_top_spenders_share():
    top = top_spenders(_records(), n=2)
    assert top[0]["service"] == "db"
    assert top[0]["share"] == 600 / 1200
    assert top[1]["service"] == "api"
    assert len(top) == 2


def test_top_spenders_empty():
    assert top_spenders([]) == []


def test_month_totals():
    totals = month_totals(_records())
    assert totals == {"2026-10": 800, "2026-09": 400}


def test_mom_change():
    change = mom_change(_records(), "2026-10", "2026-09")
    assert change["current"] == 800
    assert change["previous"] == 400
    assert change["delta"] == 400
    assert change["pct"] == 1.0


def test_mom_change_missing_month():
    assert mom_change(_records(), "2026-11", "2026-10") is None


def test_over_budget():
    over = over_budget(_records(), {"api": 450, "db": 700, "cache": 50})
    assert [o["service"] for o in over] == ["api", "cache"]
    assert over[0]["over"] == 50
    assert over[1]["over"] == 50


def test_over_budget_none_within():
    assert over_budget(_records(), {"api": 1000, "db": 1000}) == []


def test_markdown_sections():
    md = to_markdown(
        _records(), budgets={"api": 450},
        month="2026-10", prev_month="2026-09", top_n=2,
    )
    assert "# Cost report" in md
    assert "Total spend: 1,200.00" in md
    assert "| db | 600.00 | 50.0% |" in md
    assert "2026-10: 800.00 vs 2026-09: 400.00 (+400.00, +100.0%)" in md
    assert "## Over budget" in md
    assert "- api: spent 500.00 on a 450.00 budget (over by 50.00)" in md


def test_markdown_all_within_budget():
    md = to_markdown(_records(), budgets={"api": 1000})
    assert "All services within budget." in md


def test_markdown_mom_no_data():
    md = to_markdown(_records(), month="2026-11", prev_month="2026-10")
    assert "No data for 2026-11 vs 2026-10." in md


def test_records_from_json_defaults():
    records = records_from_json([{"service": "x"}])
    assert records[0].amount == 0
    assert records[0].month == ""
