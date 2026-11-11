from datetime import date

from sre_toolkit.vuln import (
    check_vulns,
    findings_from_json,
    sla_for,
    to_markdown,
    Finding,
)

TODAY = date(2026, 11, 11)


def _finding(**kwargs) -> Finding:
    defaults = dict(
        id="CVE-2026-0001", severity="high", service="api",
        discovered="2026-10-20",
    )
    defaults.update(kwargs)
    return Finding(**defaults)


def test_sla_defaults():
    assert sla_for("critical") == 7
    assert sla_for("high") == 30
    assert sla_for("medium") == 90
    assert sla_for("low") == 180
    assert sla_for("unknown-severity") == 90


def test_ok_finding():
    results = check_vulns([_finding()], TODAY)
    assert results[0].status == "ok"
    assert results[0].days_open == 22
    assert results[0].sla_days == 30


def test_overdue_finding():
    results = check_vulns([_finding(severity="critical", discovered="2026-10-20")], TODAY)
    assert results[0].status == "overdue"
    assert results[0].days_open == 22
    assert results[0].sla_days == 7


def test_due_soon_finding():
    # high, 30-day SLA, 25 days open -> due (within 7 days)
    results = check_vulns([_finding(discovered="2026-10-17")], TODAY)
    assert results[0].status == "due"


def test_boundary_exactly_sla_is_due():
    results = check_vulns([_finding(discovered="2026-10-12")], TODAY)
    assert results[0].status == "due"


def test_custom_sla_days():
    results = check_vulns([_finding(sla_days=10)], TODAY)
    assert results[0].sla_days == 10
    assert results[0].status == "overdue"


def test_unknown_discovered_date():
    results = check_vulns([_finding(discovered="sometime")], TODAY)
    assert results[0].status == "unknown"
    assert results[0].days_open is None


def test_markdown_sorted_critical_first():
    findings = [
        _finding(id="LOW-1", severity="low", discovered="2026-11-01"),
        _finding(id="CRIT-1", severity="critical", discovered="2026-11-10"),
        _finding(id="HIGH-1", severity="high", discovered="2026-10-20"),
    ]
    md = to_markdown(check_vulns(findings, TODAY))
    assert "Findings checked: 3" in md
    assert "- Overdue: 0" in md
    assert "- Due soon: 1" in md
    assert md.index("CRIT-1") < md.index("HIGH-1") < md.index("LOW-1")
    assert "| CRIT-1 | critical | api | 1 | 7 | due |" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "Findings checked: 0" in md
    assert "No findings to check." in md


def test_findings_from_json_defaults():
    findings = findings_from_json([{"id": "x"}])
    assert findings[0].severity == "medium"
    assert findings[0].sla_days is None
