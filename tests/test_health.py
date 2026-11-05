from sre_toolkit.health import (
    HealthCheck,
    checks_from_json,
    overall_status,
    slowest,
    to_markdown,
)


def _checks() -> list:
    return [
        HealthCheck("api", "up", 120),
        HealthCheck("db", "degraded", 450),
        HealthCheck("cache", "down"),
    ]


def test_overall_worst_wins():
    assert overall_status(_checks()) == "down"


def test_overall_degraded_when_no_down():
    assert overall_status([HealthCheck("a", "up"), HealthCheck("b", "degraded")]) == "degraded"


def test_overall_up_when_all_up():
    assert overall_status([HealthCheck("a", "up")]) == "up"


def test_overall_up_when_empty():
    assert overall_status([]) == "up"


def test_overall_unknown_status_treated_as_up():
    assert overall_status([HealthCheck("a", "weird")]) == "up"


def test_slowest():
    slow = slowest(_checks())
    assert slow is not None
    assert slow.service == "db"
    assert slow.latency_ms == 450


def test_slowest_none_without_latencies():
    assert slowest([HealthCheck("a", "up")]) is None


def test_markdown_sections():
    md = to_markdown(_checks())
    assert "# Service health" in md
    assert "Overall: **down**" in md
    assert "Checked 3 services: 1 degraded, 1 down, 1 up" in md
    assert "Slowest: db (450ms)" in md
    assert "| cache | down | - |" in md
    assert "## Needs attention" in md
    assert "- db: degraded" in md
    assert "- cache: down" in md


def test_markdown_all_up_message():
    md = to_markdown([HealthCheck("a", "up", 50)])
    assert "All services up." in md


def test_checks_from_json_defaults():
    checks = checks_from_json([{"service": "x"}])
    assert checks[0].status == "up"
    assert checks[0].latency_ms is None
