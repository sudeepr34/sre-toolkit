"""Change-freeze gate for deployments.

Answers the on-call question "can I deploy right now?" against a freeze
calendar. The calendar mixes explicit blackout windows (holidays, launch
freezes) and weekly recurring freezes (e.g. no weekend deploys). The CLI
exits 0 when deploys are allowed and 1 when blocked, so it can gate a
pipeline directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta


def _parse_dt(value: str) -> datetime:
    """Parse an ISO-ish datetime; raises ValueError when unparseable."""
    candidate = value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(candidate)


def parse_datetime(value: str) -> datetime:
    """Public alias for parsing an ISO-ish datetime (used by the CLI)."""
    return _parse_dt(value)


def _parse_time(value: str) -> time:
    """Parse an HH:MM time; raises ValueError when unparseable."""
    return datetime.strptime(value.strip(), "%H:%M").time()


@dataclass
class FreezeWindow:
    """An explicit blackout window. Start is inclusive, end is exclusive."""

    name: str
    start: datetime
    end: datetime
    reason: str = ""

    def contains(self, moment: datetime) -> bool:
        return self.start <= moment < self.end


@dataclass
class WeeklyFreeze:
    """A freeze recurring every week, e.g. Friday 18:00 -> Monday 09:00.

    ``weekday``/``end_weekday`` follow datetime.weekday() (Monday=0).
    """

    name: str
    weekday: int
    start_time: time
    end_weekday: int
    end_time: time
    reason: str = ""

    def _occurrence_start(self, moment: datetime) -> datetime:
        """Start of the latest weekly occurrence at or before ``moment``."""
        latest: datetime | None = None
        for days_back in range(8):
            day = (moment - timedelta(days=days_back)).date()
            if day.weekday() == self.weekday:
                candidate = datetime.combine(day, self.start_time)
                if candidate <= moment and (latest is None or candidate > latest):
                    latest = candidate
        assert latest is not None  # one weekday always matches within 8 days
        return latest

    def current_window(self, moment: datetime) -> FreezeWindow:
        """The concrete FreezeWindow of the occurrence covering ``moment``."""
        start = self._occurrence_start(moment)
        days = (self.end_weekday - self.weekday) % 7
        end = datetime.combine(start.date() + timedelta(days=days), self.end_time)
        if end <= start:
            end += timedelta(days=7)
        return FreezeWindow(
            name=self.name, start=start, end=end, reason=self.reason
        )

    def contains(self, moment: datetime) -> bool:
        return self.current_window(moment).contains(moment)


@dataclass
class GateResult:
    allowed: bool
    blocking: FreezeWindow | None = None

    def to_markdown(self) -> str:
        if self.allowed:
            return "# Deploy gate: ALLOWED\n\nNo freeze window is active.\n"
        window = self.blocking
        assert window is not None
        lines = ["# Deploy gate: BLOCKED", ""]
        lines.append(f"- Frozen by: **{window.name}**")
        lines.append(f"- Window: {window.start} -> {window.end}")
        if window.reason:
            lines.append(f"- Reason: {window.reason}")
        lines.append("- Recommendation: hold the deploy until the window ends.")
        return "\n".join(lines) + "\n"


@dataclass
class DeployGate:
    freezes: list = field(default_factory=list)

    def check(self, moment: datetime) -> GateResult:
        for freeze in self.freezes:
            if isinstance(freeze, WeeklyFreeze):
                window = freeze.current_window(moment)
            else:
                window = freeze
            if window.contains(moment):
                return GateResult(allowed=False, blocking=window)
        return GateResult(allowed=True)

    def active_freezes(self, moment: datetime) -> list[FreezeWindow]:
        """All windows active at ``moment``, as concrete FreezeWindows."""
        active = []
        for freeze in self.freezes:
            window = (
                freeze.current_window(moment)
                if isinstance(freeze, WeeklyFreeze)
                else freeze
            )
            if window.contains(moment):
                active.append(window)
        return active


def _freeze_from_dict(raw: dict) -> FreezeWindow | WeeklyFreeze:
    kind = raw.get("kind", "explicit")
    if kind == "weekly":
        return WeeklyFreeze(
            name=raw.get("name", "weekly freeze"),
            weekday=int(raw["weekday"]),
            start_time=_parse_time(raw["start_time"]),
            end_weekday=int(raw["end_weekday"]),
            end_time=_parse_time(raw["end_time"]),
            reason=raw.get("reason", ""),
        )
    return FreezeWindow(
        name=raw.get("name", "freeze"),
        start=_parse_dt(raw["start"]),
        end=_parse_dt(raw["end"]),
        reason=raw.get("reason", ""),
    )


def deploy_gate_from_dict(data: dict) -> DeployGate:
    """Build a DeployGate from a JSON-ish dict; unknown keys are ignored."""
    freezes = [_freeze_from_dict(raw) for raw in data.get("freezes", [])]
    return DeployGate(freezes=freezes)
