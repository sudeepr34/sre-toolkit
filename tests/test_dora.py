from datetime import date

import pytest

from sre_toolkit.dora import (
    change_failure_rate,
    deployment_frequency,
    in_window,
    mean_lead_time_hours,
    per_service,
    records_from_json,
    to_markdown,
    DeployRecord,
)


def _records() -> list:
    return [
        DeployRecord("api", "2026-10-10", "success", 4.0),
        DeployRecord("api", "2026-10-15", "failed", 6.0),
        DeployRecord("api", "2026-10-20", "success", 2.0),
        DeployRecord("web", "2026-10-22", "success", 3.0),
        DeployRecord("web", "2026-09-01", "success", 3.0),  # outside window
        DeployRecord("db", "not-a-date", "success"),
    ]


def test_in_window_filters():
    window = in_window(_records(), date(2026, 10, 1), date(2026, 10, 31))
    assert len(window) == 4
    assert all(r.timestamp.startswith("2026-10") for r in window)


def test_deployment_frequency():
    # 4 deploys in 28 days -> 1.0 per week
    assert deployment_frequency(_records()[:4], 28) == pytest.approx(1.0)


def test_deployment_frequency_zero_days():
    assert deployment_frequency(_records(), 0) == 0.0


def test_change_failure_rate():
    assert change_failure_rate(_records()[:4]) == pytest.approx(25.0)


def test_change_failure_rate_none_when_empty():
    assert change_failure_rate([]) is None


def test_mean_lead_time():
    assert mean_lead_time_hours(_records()[:4]) == pytest.approx(3.75)


def test_mean_lead_time_none_when_unreported():
    assert mean_lead_time_hours([DeployRecord("x", "2026-10-10")]) is None


def test_per_service_sorted():
    result = per_service(_records()[:4])
    assert result == [("api", 3, 1), ("web", 1, 0)]


def test_markdown_sections():
    window = in_window(_records(), date(2026, 10, 1), date(2026, 10, 31))
    md = to_markdown(window, date(2026, 10, 1), date(2026, 10, 31))
    assert "# DORA metrics" in md
    assert "Window: 2026-10-01 to 2026-10-31 (31 days)" in md
    assert "Deploys: 4" in md
    assert "Deployment frequency: 0.90 per week" in md
    assert "Change failure rate: 25.0%" in md
    assert "Mean lead time: 3.8 hours" in md
    assert "| api | 3 | 1 |" in md


def test_markdown_empty_window():
    md = to_markdown([], date(2026, 10, 1), date(2026, 10, 31))
    assert "Deploys: 0" in md
    assert "Change failure rate: n/a (no deploys)" in md


def test_records_from_json_defaults():
    records = records_from_json([{"service": "x", "timestamp": "2026-10-10"}])
    assert records[0].status == "success"
    assert records[0].lead_time_hours is None
