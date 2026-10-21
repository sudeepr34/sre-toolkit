"""On-call rotation lookup.

Given a round-robin rotation (ordered members, a shift length in days,
and the date the first member's first shift started), answers who's on
call at a given moment, the current shift window, and who's up next.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta


def _parse_date(value: str) -> date:
    """Parse a YYYY-MM-DD date; raises ValueError when unparseable."""
    return date.fromisoformat(value.strip())


def parse_date(value: str) -> date:
    """Public alias for parsing a YYYY-MM-DD date (used by the CLI)."""
    return _parse_date(value)


@dataclass
class Rotation:
    name: str
    members: list = field(default_factory=list)
    start_date: date = field(default_factory=date.today)
    shift_days: int = 7

    def __post_init__(self) -> None:
        if not self.members:
            raise ValueError(f"rotation {self.name!r} needs at least one member")
        if self.shift_days <= 0:
            raise ValueError(f"shift_days must be > 0, got {self.shift_days}")

    def _shift_index(self, moment: date) -> int:
        days = (moment - self.start_date).days
        if days < 0:
            raise ValueError(
                f"{moment} is before the rotation start {self.start_date}"
            )
        return (days // self.shift_days) % len(self.members)

    def who_is_on(self, moment: date) -> str:
        """The member holding the pager on ``moment``."""
        return self.members[self._shift_index(moment)]

    def shift_window(self, moment: date) -> tuple[date, date]:
        """(start, end) of the shift covering ``moment``; end is exclusive."""
        self._shift_index(moment)  # validates moment is within the rotation
        days = (moment - self.start_date).days
        shift_no = days // self.shift_days
        start = self.start_date + timedelta(days=shift_no * self.shift_days)
        return start, start + timedelta(days=self.shift_days)

    def upcoming(self, moment: date, count: int = 3) -> list[tuple[str, date]]:
        """Next ``count`` shifts as (member, start date) pairs, starting now."""
        if count < 0:
            raise ValueError(f"count must be >= 0, got {count}")
        days = (moment - self.start_date).days
        if days < 0:
            raise ValueError(
                f"{moment} is before the rotation start {self.start_date}"
            )
        current_no = days // self.shift_days
        result = []
        for offset in range(count):
            shift_no = current_no + offset
            member = self.members[shift_no % len(self.members)]
            start = self.start_date + timedelta(days=shift_no * self.shift_days)
            result.append((member, start))
        return result

    def to_markdown(self, moment: date) -> str:
        current = self.who_is_on(moment)
        start, end = self.shift_window(moment)
        lines = [f"# On-call: {self.name}", ""]
        lines.append(f"- Date: {moment}")
        lines.append(f"- On call now: **{current}** (shift {start} -> {end})")
        upcoming = self.upcoming(moment, 3)[1:]
        if upcoming:
            lines.append("")
            lines.append("## Up next")
            for member, shift_start in upcoming:
                lines.append(f"- {shift_start}: {member}")
        return "\n".join(lines) + "\n"


def rotation_from_dict(data: dict) -> Rotation:
    """Build a Rotation from a JSON-ish dict; unknown keys are ignored."""
    return Rotation(
        name=data.get("name", "rotation"),
        members=list(data.get("members", [])),
        start_date=_parse_date(data["start_date"]) if "start_date" in data else date.today(),
        shift_days=int(data.get("shift_days", 7)),
    )
