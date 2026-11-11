"""On-call coverage gaps.

A rotation with a hole in it pages nobody. This checks a JSON list of
on-call shifts against a date range and finds uncovered days, so the
gap is filled before the pager goes quiet at 2 a.m.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class Shift:
    person: str
    start: str  # ISO date, inclusive
    end: str  # ISO date, inclusive


@dataclass
class Gap:
    start: date
    end: date

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip()[:10])
    except (ValueError, AttributeError):
        return None


def _merged_intervals(shifts: list, start: date, end: date) -> list:
    intervals = []
    for shift in shifts:
        shift_start = _parse_date(shift.start)
        shift_end = _parse_date(shift.end)
        if shift_start is None or shift_end is None or shift_end < shift_start:
            continue
        intervals.append((max(shift_start, start), min(shift_end, end)))
    intervals = [iv for iv in intervals if iv[0] <= iv[1]]
    intervals.sort()
    merged: list = []
    for interval in intervals:
        if merged and interval[0] <= merged[-1][1] + timedelta(days=1):
            merged[-1] = (merged[-1][0], max(merged[-1][1], interval[1]))
        else:
            merged.append(interval)
    return merged


def find_gaps(shifts: list, start: date, end: date) -> list:
    """Uncovered date ranges inside [start, end]."""
    if end < start:
        return []
    gaps = []
    cursor = start
    for interval_start, interval_end in _merged_intervals(shifts, start, end):
        if interval_start > cursor:
            gaps.append(Gap(cursor, interval_start - timedelta(days=1)))
        cursor = max(cursor, interval_end + timedelta(days=1))
    if cursor <= end:
        gaps.append(Gap(cursor, end))
    return gaps


def coverage_pct(shifts: list, start: date, end: date) -> float:
    total = (end - start).days + 1
    if total <= 0:
        return 0.0
    covered = sum(
        (iv_end - iv_start).days + 1
        for iv_start, iv_end in _merged_intervals(shifts, start, end)
    )
    return covered / total * 100


def to_markdown(shifts: list, gaps: list, start: date, end: date) -> str:
    lines = ["# On-call coverage", ""]
    lines.append(f"- Range: {start.isoformat()} to {end.isoformat()}")
    lines.append(f"- Shifts: {len(shifts)}")
    lines.append(f"- Coverage: {coverage_pct(shifts, start, end):.1f}%")
    lines.append(f"- Gaps found: {len(gaps)}")
    lines.append("")
    if not gaps:
        lines.append("Full coverage: every day in the range has an on-call.")
        return "\n".join(lines) + "\n"
    lines.append("## Gaps")
    lines.append("| Start | End | Days |")
    lines.append("| ----- | --- | ---- |")
    for gap in gaps:
        lines.append(f"| {gap.start.isoformat()} | {gap.end.isoformat()} | {gap.days} |")
    return "\n".join(lines) + "\n"


def shifts_from_json(data: list) -> list:
    return [
        Shift(
            person=item.get("person", "unnamed"),
            start=item.get("start", ""),
            end=item.get("end", ""),
        )
        for item in data
    ]
