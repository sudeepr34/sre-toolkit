"""Change collision detection.

Two changes on the same service at the same time is how a routine
deploy becomes a mystery outage. This checks a JSON list of scheduled
changes and flags overlapping windows on the same service, so the
conflict is caught in the calendar instead of in the incident channel.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Change:
    id: str
    service: str
    start: str  # ISO datetime
    end: str  # ISO datetime
    owner: str = ""


@dataclass
class Collision:
    first: Change
    second: Change


def _parse_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        return None


def _overlaps(first: Change, second: Change) -> bool:
    start_a = _parse_datetime(first.start)
    end_a = _parse_datetime(first.end)
    start_b = _parse_datetime(second.start)
    end_b = _parse_datetime(second.end)
    if None in (start_a, end_a, start_b, end_b):
        return False
    return start_a < end_b and start_b < end_a


def find_collisions(changes: list) -> list:
    collisions = []
    for index, first in enumerate(changes):
        for second in changes[index + 1:]:
            if first.service == second.service and _overlaps(first, second):
                collisions.append(Collision(first, second))
    return collisions


def to_markdown(changes: list, collisions: list) -> str:
    lines = ["# Change collision check", ""]
    lines.append(f"- Changes checked: {len(changes)}")
    lines.append(f"- Collisions found: {len(collisions)}")
    lines.append("")
    if not collisions:
        lines.append("No collisions: no two changes overlap on the same service.")
        return "\n".join(lines) + "\n"
    lines.append("## Collisions")
    lines.append("| Service | Change A | Change B | Window A | Window B |")
    lines.append("| ------- | -------- | -------- | -------- | -------- |")
    for collision in collisions:
        first, second = collision.first, collision.second
        lines.append(
            f"| {first.service} | {first.id} | {second.id} "
            f"| {first.start}–{first.end} | {second.start}–{second.end} |"
        )
    return "\n".join(lines) + "\n"


def changes_from_json(data: list) -> list:
    return [
        Change(
            id=item.get("id", "unnamed"),
            service=item.get("service", "unnamed"),
            start=item.get("start", ""),
            end=item.get("end", ""),
            owner=item.get("owner", ""),
        )
        for item in data
    ]
