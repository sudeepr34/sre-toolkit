"""Status-page update drafter for incidents.

Turns incident state into a customer-facing status page update in Markdown:
the current status banner, the impacted components, and the update
timeline (newest first). Pairs with ``postmortem``: comms runs while the
incident is open, postmortem after it closes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

STATUSES = ("investigating", "identified", "monitoring", "resolved")


def _parse_ts(value: str) -> datetime:
    """Parse an ISO-ish timestamp; raises ValueError when unparseable."""
    return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))


@dataclass
class StatusUpdate:
    """One customer-facing update in the incident timeline."""

    timestamp: str
    status: str
    message: str


@dataclass
class StatusPage:
    """A status-page draft for an ongoing (or recently closed) incident."""

    title: str
    status: str = "investigating"
    severity: str = "SEV-3"
    affected: list = field(default_factory=list)
    started: str = ""
    resolved: str = ""
    updates: list = field(default_factory=list)
    next_update: str = ""

    def ordered_updates(self) -> list:
        """Updates newest-first; unparsable timestamps sink to the end."""
        good: list = []
        bad: list = []
        for update in self.updates:
            try:
                good.append((_parse_ts(update.timestamp), update))
            except ValueError:
                bad.append(update)
        good.sort(key=lambda pair: pair[0], reverse=True)
        return [update for _, update in good] + bad

    def to_markdown(self) -> str:
        lines = [f"# {self.title}", ""]
        lines.append(f"- Status: **{self.status}**")
        lines.append(f"- Severity: {self.severity}")
        if self.started:
            lines.append(f"- Started: {self.started}")
        if self.resolved:
            lines.append(f"- Resolved: {self.resolved}")
        if self.affected:
            lines.append(f"- Impacted: {', '.join(self.affected)}")
        lines.append("")
        lines.append("## Updates")
        lines.append("")
        if not self.updates:
            lines.append("_No updates published yet._")
        else:
            for update in self.ordered_updates():
                lines.append(f"### {update.timestamp} — {update.status}")
                lines.append("")
                lines.append(update.message.strip())
                lines.append("")
        if self.next_update:
            lines.append(f"Next update: {self.next_update}")
            lines.append("")
        return "\n".join(lines).rstrip("\n") + "\n"


def status_page_from_dict(data: dict) -> StatusPage:
    """Build a StatusPage from a JSON-ish dict; unknown keys are ignored."""
    status = str(data.get("status", "investigating")).lower()
    if status not in STATUSES:
        raise ValueError(
            f"unknown status {status!r}; expected one of {', '.join(STATUSES)}"
        )
    updates = []
    for raw in data.get("updates", []):
        update_status = str(raw.get("status", status)).lower()
        if update_status not in STATUSES:
            raise ValueError(f"unknown update status {update_status!r}")
        updates.append(
            StatusUpdate(
                timestamp=raw.get("timestamp", ""),
                status=update_status,
                message=raw.get("message", ""),
            )
        )
    affected = data.get("affected", [])
    if isinstance(affected, str):
        affected = [affected]
    return StatusPage(
        title=data.get("title", "untitled incident"),
        status=status,
        severity=data.get("severity", "SEV-3"),
        affected=list(affected),
        started=data.get("started", ""),
        resolved=data.get("resolved", ""),
        updates=updates,
        next_update=data.get("next_update", ""),
    )
