from datetime import datetime

from sre_toolkit.maintenance import (
    check_window,
    freezes_from_json,
    to_markdown,
    FreezeWindow,
)

FREEZES = [
    FreezeWindow("black-friday", "2026-11-27T00:00:00", "2026-11-30T23:59:59", "peak traffic"),
    FreezeWindow("year-end", "2026-12-24T00:00:00", "2027-01-02T23:59:59", "holiday freeze"),
]


def test_no_conflict_outside_freeze():
    conflicts = check_window("api", "2026-11-12T02:00:00", "2026-11-12T04:00:00", FREEZES)
    assert conflicts == []


def test_conflict_inside_freeze():
    conflicts = check_window("api", "2026-11-28T02:00:00", "2026-11-28T04:00:00", FREEZES)
    assert len(conflicts) == 1
    assert conflicts[0].freeze.name == "black-friday"
    assert conflicts[0].overlap_start == datetime(2026, 11, 28, 2, 0)
    assert conflicts[0].overlap_end == datetime(2026, 11, 28, 4, 0)


def test_partial_overlap_reports_overlap_only():
    conflicts = check_window("api", "2026-11-30T20:00:00", "2026-12-01T04:00:00", FREEZES)
    assert len(conflicts) == 1
    assert conflicts[0].overlap_start == datetime(2026, 11, 30, 20, 0)
    assert conflicts[0].overlap_end == datetime(2026, 11, 30, 23, 59, 59)


def test_touching_freeze_is_not_a_conflict():
    conflicts = check_window("api", "2026-11-30T23:59:59", "2026-12-01T02:00:00", FREEZES)
    assert conflicts == []


def test_multiple_conflicts():
    conflicts = check_window("api", "2026-11-27T00:00:00", "2027-01-02T00:00:00", FREEZES)
    assert [c.freeze.name for c in conflicts] == ["black-friday", "year-end"]


def test_reversed_window_no_conflicts():
    conflicts = check_window("api", "2026-11-28T04:00:00", "2026-11-28T02:00:00", FREEZES)
    assert conflicts == []


def test_bad_dates_no_conflicts():
    conflicts = check_window("api", "soon", "2026-11-28T04:00:00", FREEZES)
    assert conflicts == []


def test_markdown_clean():
    md = to_markdown("api", "2026-11-12T02:00:00", "2026-11-12T04:00:00", [])
    assert "Conflicts found: 0" in md
    assert "Clear: the window does not overlap any freeze." in md


def test_markdown_conflicts_table():
    conflicts = check_window("api", "2026-11-28T02:00:00", "2026-11-28T04:00:00", FREEZES)
    md = to_markdown("api", "2026-11-28T02:00:00", "2026-11-28T04:00:00", conflicts)
    assert "Conflicts found: 1" in md
    assert "| black-friday | peak traffic | 2026-11-28T02:00:00–2026-11-28T04:00:00 |" in md


def test_freezes_from_json_defaults():
    freezes = freezes_from_json([{"name": "f", "start": "2026-11-27T00:00:00", "end": "2026-11-30T00:00:00"}])
    assert freezes[0].reason == ""
