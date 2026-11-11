from datetime import date

import pytest

from sre_toolkit.schedule import (
    coverage_pct,
    find_gaps,
    shifts_from_json,
    to_markdown,
    Shift,
)

START = date(2026, 11, 1)
END = date(2026, 11, 30)


def _shift(person: str, start: str, end: str) -> Shift:
    return Shift(person, start, end)


def test_full_coverage_no_gaps():
    shifts = [_shift("a", "2026-11-01", "2026-11-15"), _shift("b", "2026-11-16", "2026-11-30")]
    assert find_gaps(shifts, START, END) == []
    assert coverage_pct(shifts, START, END) == pytest.approx(100.0)


def test_single_gap():
    shifts = [_shift("a", "2026-11-01", "2026-11-10"), _shift("b", "2026-11-15", "2026-11-30")]
    gaps = find_gaps(shifts, START, END)
    assert len(gaps) == 1
    assert gaps[0].start == date(2026, 11, 11)
    assert gaps[0].end == date(2026, 11, 14)
    assert gaps[0].days == 4
    assert coverage_pct(shifts, START, END) == pytest.approx(26 / 30 * 100)


def test_gap_at_start_and_end():
    shifts = [_shift("a", "2026-11-05", "2026-11-25")]
    gaps = find_gaps(shifts, START, END)
    assert [(g.start, g.end) for g in gaps] == [
        (date(2026, 11, 1), date(2026, 11, 4)),
        (date(2026, 11, 26), date(2026, 11, 30)),
    ]


def test_no_shifts_whole_range_is_gap():
    gaps = find_gaps([], START, END)
    assert len(gaps) == 1
    assert gaps[0].days == 30
    assert coverage_pct([], START, END) == pytest.approx(0.0)


def test_overlapping_shifts_merge():
    shifts = [
        _shift("a", "2026-11-01", "2026-11-20"),
        _shift("b", "2026-11-10", "2026-11-30"),
    ]
    assert find_gaps(shifts, START, END) == []


def test_adjacent_shifts_no_gap():
    shifts = [_shift("a", "2026-11-01", "2026-11-15"), _shift("b", "2026-11-16", "2026-11-30")]
    assert find_gaps(shifts, START, END) == []


def test_bad_dates_ignored():
    shifts = [_shift("a", "soon", "2026-11-30"), _shift("b", "2026-11-01", "2026-11-15")]
    gaps = find_gaps(shifts, START, END)
    assert len(gaps) == 1
    assert gaps[0].start == date(2026, 11, 16)


def test_reversed_range_no_gaps():
    assert find_gaps([_shift("a", "2026-11-01", "2026-11-30")], END, START) == []


def test_markdown_sections():
    shifts = [_shift("a", "2026-11-01", "2026-11-10"), _shift("b", "2026-11-15", "2026-11-30")]
    md = to_markdown(shifts, find_gaps(shifts, START, END), START, END)
    assert "Range: 2026-11-01 to 2026-11-30" in md
    assert "Coverage: 86.7%" in md
    assert "Gaps found: 1" in md
    assert "| 2026-11-11 | 2026-11-14 | 4 |" in md


def test_shifts_from_json_defaults():
    shifts = shifts_from_json([{"person": "a"}])
    assert shifts[0].start == ""
    assert shifts[0].end == ""
