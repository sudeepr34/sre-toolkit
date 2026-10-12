"""Generate on-call handoff notes that don't lose the thread.

Shift changes are where follow-ups die. A Handoff captures the outgoing
shift's open incidents, things to watch, pending follow-ups and recent
changes, and renders them as Markdown for the on-call channel, so the
incoming shift starts with the full picture instead of archaeology.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OpenIncident:
    title: str
    severity: str = "SEV-3"
    status: str = "mitigated"
    owner: str = "on-call"


@dataclass
class FollowUp:
    task: str
    owner: str = "on-call"
    due: str = ""


@dataclass
class Handoff:
    shift: str = ""
    outgoing: str = "on-call"
    incoming: str = "on-call"
    open_incidents: list[OpenIncident] = field(default_factory=list)
    watch_items: list[str] = field(default_factory=list)
    follow_ups: list[FollowUp] = field(default_factory=list)
    recent_changes: list[str] = field(default_factory=list)

    def add_incident(self, title: str, **kwargs: str) -> OpenIncident:
        incident = OpenIncident(title=title, **kwargs)
        self.open_incidents.append(incident)
        return incident

    def add_follow_up(self, task: str, **kwargs: str) -> FollowUp:
        follow_up = FollowUp(task=task, **kwargs)
        self.follow_ups.append(follow_up)
        return follow_up

    @property
    def open_count(self) -> int:
        return sum(1 for i in self.open_incidents if i.status != "resolved")

    def to_markdown(self) -> str:
        lines = [f"# On-call handoff: {self.shift or 'this shift'}", ""]
        lines.append(f"- Outgoing: {self.outgoing}")
        lines.append(f"- Incoming: {self.incoming}")
        lines.append("")

        lines.append("## Open incidents")
        if self.open_incidents:
            for incident in self.open_incidents:
                lines.append(
                    f"- [{incident.severity}] {incident.title} "
                    f"({incident.status}, owner: {incident.owner})"
                )
        else:
            lines.append("- None")
        lines.append("")

        lines.append("## Watch items")
        if self.watch_items:
            for item in self.watch_items:
                lines.append(f"- {item}")
        else:
            lines.append("- None")
        lines.append("")

        lines.append("## Pending follow-ups")
        if self.follow_ups:
            for follow_up in self.follow_ups:
                due = f", due: {follow_up.due}" if follow_up.due else ""
                lines.append(f"- {follow_up.task} (owner: {follow_up.owner}{due})")
        else:
            lines.append("- None")
        lines.append("")

        lines.append("## Recent changes")
        if self.recent_changes:
            for change in self.recent_changes:
                lines.append(f"- {change}")
        else:
            lines.append("- None")

        return "\n".join(lines)


def handoff_from_dict(data: dict) -> Handoff:
    """Build a Handoff from a plain dict (e.g. loaded from a JSON file).

    Accepted keys: shift, outgoing, incoming, open_incidents (list of
    dicts), watch_items (list of str), follow_ups (list of dicts),
    recent_changes (list of str). Unknown keys are ignored.
    """
    handoff = Handoff(
        shift=data.get("shift", ""),
        outgoing=data.get("outgoing", "on-call"),
        incoming=data.get("incoming", "on-call"),
    )
    for raw in data.get("open_incidents", []):
        known = {k: raw[k] for k in ("severity", "status", "owner") if k in raw}
        handoff.add_incident(raw.get("title", ""), **known)
    handoff.watch_items.extend(data.get("watch_items", []))
    for raw in data.get("follow_ups", []):
        known = {k: raw[k] for k in ("owner", "due") if k in raw}
        handoff.add_follow_up(raw.get("task", ""), **known)
    handoff.recent_changes.extend(data.get("recent_changes", []))
    return handoff
