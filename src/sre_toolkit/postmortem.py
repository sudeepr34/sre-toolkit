"""Blameless postmortems from an incident timeline.

The runbook gets you through the incident; the postmortem makes sure the
next one goes better. A Postmortem captures the title, severity, summary,
an ordered timeline with detection/mitigation/resolution milestones,
contributing factors, what went well, and follow-up action items -- and
renders them as Markdown for the incident review.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

_MILESTONE_LABELS = {
    "detected": "DETECTED",
    "mitigated": "MITIGATED",
    "resolved": "RESOLVED",
}


def _parse_ts(ts: str) -> datetime | None:
    """Parse an ISO-ish timestamp; None when it is missing or unparseable."""
    if not ts:
        return None
    candidate = ts.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _fmt_duration(seconds: float) -> str:
    return format_duration(seconds)


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as a compact human string (5m, 1h 30m)."""
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m" if secs == 0 else f"{minutes}m {secs}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h" if minutes == 0 else f"{hours}h {minutes}m"


@dataclass
class TimelineEvent:
    timestamp: str = ""
    title: str = ""
    actor: str = "on-call"
    detail: str = ""
    milestone: str = ""  # "", "detected", "mitigated" or "resolved"

    @property
    def milestone_label(self) -> str:
        return _MILESTONE_LABELS.get(self.milestone.lower(), "")


@dataclass
class ActionItem:
    task: str
    owner: str = "on-call"
    due: str = ""
    done: bool = False


@dataclass
class Postmortem:
    title: str = "untitled incident"
    date: str = ""
    severity: str = "SEV-3"
    summary: str = ""
    timeline: list[TimelineEvent] = field(default_factory=list)
    contributing_factors: list[str] = field(default_factory=list)
    went_well: list[str] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)

    def add_event(self, timestamp: str, title: str, **kwargs: str) -> TimelineEvent:
        event = TimelineEvent(timestamp=timestamp, title=title, **kwargs)
        self.timeline.append(event)
        return event

    def add_action_item(self, task: str, **kwargs) -> ActionItem:
        item = ActionItem(task=task, **kwargs)
        self.action_items.append(item)
        return item

    def add_factor(self, factor: str) -> None:
        self.contributing_factors.append(factor)

    def add_went_well(self, item: str) -> None:
        self.went_well.append(item)

    def _milestone_ts(self, name: str) -> datetime | None:
        for event in sorted(self.timeline, key=lambda e: e.timestamp):
            if event.milestone.lower() == name:
                parsed = _parse_ts(event.timestamp)
                if parsed is not None:
                    return parsed
        return None

    @property
    def time_to_mitigate_seconds(self) -> float | None:
        """Detected -> mitigated span in seconds, None when milestones missing."""
        detected = self._milestone_ts("detected")
        mitigated = self._milestone_ts("mitigated")
        if detected is None or mitigated is None:
            return None
        return (mitigated - detected).total_seconds()

    @property
    def time_to_mitigate(self) -> str | None:
        """Detected -> mitigated span, or None when milestones are missing."""
        seconds = self.time_to_mitigate_seconds
        return _fmt_duration(seconds) if seconds is not None else None

    @property
    def time_to_resolve_seconds(self) -> float | None:
        """Detected -> resolved span in seconds, None when milestones missing."""
        detected = self._milestone_ts("detected")
        resolved = self._milestone_ts("resolved")
        if detected is None or resolved is None:
            return None
        return (resolved - detected).total_seconds()

    @property
    def time_to_resolve(self) -> str | None:
        """Detected -> resolved span, or None when milestones are missing."""
        seconds = self.time_to_resolve_seconds
        return _fmt_duration(seconds) if seconds is not None else None

    @property
    def open_action_items(self) -> int:
        return sum(1 for item in self.action_items if not item.done)

    def to_markdown(self) -> str:
        lines = [f"# Postmortem: {self.title}", ""]
        meta = f"- Date: {self.date or 'unspecified'} | Severity: {self.severity}"
        lines.append(meta)
        lines.append("")

        lines.append("## Summary")
        lines.append(self.summary if self.summary else "_No summary yet._")
        lines.append("")

        lines.append("## Timeline")
        if self.timeline:
            for event in sorted(self.timeline, key=lambda e: e.timestamp):
                tag = (
                    f" **[{event.milestone_label}]**"
                    if event.milestone_label
                    else ""
                )
                line = f"- {event.timestamp or '?'} {event.title}{tag} ({event.actor})"
                lines.append(line)
                if event.detail:
                    lines.append(f"  > {event.detail}")
        else:
            lines.append("- _No timeline events yet._")
        lines.append("")

        metrics = []
        if self.time_to_mitigate is not None:
            metrics.append(f"- Time to mitigate: {self.time_to_mitigate}")
        if self.time_to_resolve is not None:
            metrics.append(f"- Time to resolve: {self.time_to_resolve}")
        if metrics:
            lines.append("## Key metrics")
            lines.extend(metrics)
            lines.append("")

        lines.append("## Contributing factors")
        if self.contributing_factors:
            lines.extend(f"- {factor}" for factor in self.contributing_factors)
        else:
            lines.append("- _None recorded._")
        lines.append("")

        lines.append("## What went well")
        if self.went_well:
            lines.extend(f"- {item}" for item in self.went_well)
        else:
            lines.append("- _None recorded._")
        lines.append("")

        lines.append(
            f"## Action items ({self.open_action_items} open)"
        )
        if self.action_items:
            for item in self.action_items:
                box = "x" if item.done else " "
                due = f", due: {item.due}" if item.due else ""
                lines.append(f"- [{box}] {item.task} (owner: {item.owner}{due})")
        else:
            lines.append("- _None recorded._")

        return "\n".join(lines) + "\n"


def postmortem_from_dict(data: dict) -> Postmortem:
    """Build a Postmortem from a JSON-ish dict; unknown keys are ignored."""
    postmortem = Postmortem(
        title=data.get("title", "untitled incident"),
        date=data.get("date", ""),
        severity=data.get("severity", "SEV-3"),
        summary=data.get("summary", ""),
    )
    for raw in data.get("timeline", []):
        postmortem.timeline.append(
            TimelineEvent(
                timestamp=raw.get("timestamp", ""),
                title=raw.get("title", ""),
                actor=raw.get("actor", "on-call"),
                detail=raw.get("detail", ""),
                milestone=raw.get("milestone", ""),
            )
        )
    postmortem.contributing_factors.extend(data.get("contributing_factors", []))
    postmortem.went_well.extend(data.get("went_well", []))
    for raw in data.get("action_items", []):
        postmortem.action_items.append(
            ActionItem(
                task=raw.get("task", ""),
                owner=raw.get("owner", "on-call"),
                due=raw.get("due", ""),
                done=bool(raw.get("done", False)),
            )
        )
    return postmortem
