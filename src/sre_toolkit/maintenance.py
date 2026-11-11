"""Maintenance window checks.

A maintenance window inside a change freeze is a change that should
never have been scheduled. This checks a proposed window against a
JSON list of freeze windows and reports the conflicts, so the work is
moved instead of colliding with the freeze.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class FreezeWindow:
    name: str
    start: str  # ISO datetime
    end: str  # ISO datetime
    reason: str = ""


@dataclass
class Conflict:
    freeze: FreezeWindow
    overlap_start: datetime
    overlap_end: datetime


def _parse_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        return None


def check_window(
    service: str, start: str, end: str, freezes: list
) -> list:
    """Freeze windows overlapping the proposed [start, end) window."""
    window_start = _parse_datetime(start)
    window_end = _parse_datetime(end)
    if window_start is None or window_end is None or window_end <= window_start:
        return []
    conflicts = []
    for freeze in freezes:
        freeze_start = _parse_datetime(freeze.start)
        freeze_end = _parse_datetime(freeze.end)
        if freeze_start is None or freeze_end is None:
            continue
        if window_start < freeze_end and freeze_start < window_end:
            conflicts.append(
                Conflict(
                    freeze,
                    max(window_start, freeze_start),
                    min(window_end, freeze_end),
                )
            )
    return conflicts


def to_markdown(service: str, start: str, end: str, conflicts: list) -> str:
    lines = ["# Maintenance window check", ""]
    lines.append(f"- Service: {service}")
    lines.append(f"- Window: {start} to {end}")
    lines.append(f"- Conflicts found: {len(conflicts)}")
    lines.append("")
    if not conflicts:
        lines.append("Clear: the window does not overlap any freeze.")
        return "\n".join(lines) + "\n"
    lines.append("## Conflicts")
    lines.append("| Freeze | Reason | Overlap |")
    lines.append("| ------ | ------ | ------- |")
    for conflict in conflicts:
        lines.append(
            f"| {conflict.freeze.name} | {conflict.freeze.reason or '—'} "
            f"| {conflict.overlap_start.isoformat()}–{conflict.overlap_end.isoformat()} |"
        )
    return "\n".join(lines) + "\n"


def freezes_from_json(data: list) -> list:
    return [
        FreezeWindow(
            name=item.get("name", "unnamed"),
            start=item.get("start", ""),
            end=item.get("end", ""),
            reason=item.get("reason", ""),
        )
        for item in data
    ]
