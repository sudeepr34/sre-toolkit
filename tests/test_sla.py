import pytest

from sre_toolkit.sla import (
    check_sla,
    error_budget_minutes,
    records_from_json,
    to_markdown,
    window_minutes,
    SLARecord,
)


def test_window_minutes():
    assert window_minutes(30) == 43200


def test_budget_above_target():
    # 99.95 vs 99.9 over 30 days: 0.05% of 43200 = 21.6 minutes
    assert error_budget_minutes(99.95, 99.9, 30) == pytest.approx(21.6)


def test_budget_below_target_negative():
    # 99.5 vs 99.9 over 30 days: -0.4% of 43200 = -172.8 minutes
    assert error_budget_minutes(99.5, 99.9, 30) == pytest.approx(-172.8)


def test_budget_exactly_at_target():
    assert error_budget_minutes(99.9, 99.9, 30) == pytest.approx(0.0)


def test_check_sla_compliant():
    results = check_sla([SLARecord("api", 99.95, 99.9)])
    assert results[0].compliant is True
    assert results[0].budget_minutes == pytest.approx(21.6)


def test_check_sla_breached():
    results = check_sla([SLARecord("api", 99.5, 99.9)])
    assert results[0].compliant is False
    assert results[0].budget_minutes == pytest.approx(-172.8)


def test_check_sla_exactly_at_target_compliant():
    results = check_sla([SLARecord("api", 99.9, 99.9)])
    assert results[0].compliant is True


def test_markdown_summary():
    records = [
        SLARecord("api", 99.95, 99.9),
        SLARecord("db", 99.5, 99.9),
    ]
    md = to_markdown(check_sla(records))
    assert "Window: 30 days" in md
    assert "Services checked: 2" in md
    assert "- Compliant: 1" in md
    assert "- Breached: 1" in md
    assert "| api | 99.950% | 99.900% | 21.6 | compliant |" in md
    assert "| db | 99.500% | 99.900% | -172.8 | BREACHED |" in md


def test_records_from_json_defaults():
    records = records_from_json([{"service": "x"}])
    assert records[0].uptime_pct == 0.0
    assert records[0].target_pct == 0.0
