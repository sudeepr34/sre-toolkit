import pytest

from sre_toolkit.toil import (
    automation_candidates,
    by_category,
    by_task,
    entries_from_json,
    to_markdown,
    toil_percentage,
    total_minutes,
    ToilEntry,
)


def _entries() -> list:
    return [
        ToilEntry("restart pods", 180, "manual", "2026-10-30"),
        ToilEntry("restart pods", 60, "manual", "2026-10-29"),
        ToilEntry("rotate certs", 300, "automatable", "2026-10-30"),
        ToilEntry("incident bridge", 120, "operational", "2026-10-30"),
    ]


def test_total_minutes():
    assert total_minutes(_entries()) == 660


def test_by_task_groups_and_sorts():
    assert by_task(_entries()) == [
        ("rotate certs", 300),
        ("restart pods", 240),
        ("incident bridge", 120),
    ]


def test_by_category():
    result = dict(by_category(_entries()))
    assert result == {"manual": 240, "automatable": 300, "operational": 120}


def test_toil_percentage():
    assert toil_percentage(_entries(), 1200) == pytest.approx(55.0)


def test_toil_percentage_none_for_zero_capacity():
    assert toil_percentage(_entries(), 0) is None


def test_automation_candidates_threshold():
    candidates = automation_candidates(_entries(), min_minutes=200)
    assert candidates == [("rotate certs", 300), ("restart pods", 240)]


def test_automation_candidates_excludes_operational():
    candidates = automation_candidates(_entries(), min_minutes=100)
    tasks = [task for task, _ in candidates]
    assert "incident bridge" not in tasks


def test_automation_candidates_empty_below_threshold():
    assert automation_candidates(_entries(), min_minutes=1000) == []


def test_markdown_over_budget_flag():
    md = to_markdown(_entries(), capacity_minutes=1200)
    assert "Total toil: 660 minutes (11.0 hours)" in md
    assert "Share of capacity: 55.0%" in md
    assert "over budget by 5.0 points" in md
    assert "| rotate certs | 300 | 45.5% |" in md
    assert "- rotate certs: 300 minutes" in md


def test_markdown_within_budget_no_flag():
    md = to_markdown(_entries(), capacity_minutes=2400)
    assert "Share of capacity: 27.5%" in md
    assert "over budget" not in md


def test_markdown_no_capacity_line():
    md = to_markdown(_entries())
    assert "Share of capacity" not in md


def test_markdown_no_candidates_message():
    md = to_markdown(_entries(), min_minutes=1000)
    assert "No automation candidates above the threshold." in md


def test_entries_from_json_defaults():
    entries = entries_from_json([{"task": "x"}])
    assert entries[0].minutes == 0
    assert entries[0].category == "manual"
    assert entries[0].date == ""
