"""Live incident tracking.

Tracks active incidents in a JSON state file: start one, append timeline
notes, check status with elapsed time, list what's open, and resolve.
Pairs with ``comms`` (which drafts the customer-facing updates) and
``escalate`` (which says who to page).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from .postmortem import format_duration

STATUSES = ("open", "acknowledged", "mitigating", "resolved")


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


@dataclass
class TimelineNote:
    timestamp: str
    kind: str  # opened, status, note, resolved
    text: str


@dataclass
class Incident:
    id: str
    title: str
    severity: str = "SEV-3"
    status: str = "open"
    started: str = ""
    timeline: list = field(default_factory=list)

    def elapsed_seconds(self, now: datetime | None = None) -> float | None:
        """Seconds since the incident started; None when unparseable."""
        try:
            start = _parse_ts(self.started)
        except ValueError:
            return None
        moment = now or datetime.now()
        return max(0.0, (moment - start).total_seconds())

    def add_note(self, text: str, timestamp: str = "") -> None:
        self.timeline.append(
            TimelineNote(
                timestamp=timestamp or _now_iso(), kind="note", text=text
            )
        )

    def set_status(self, status: str, timestamp: str = "") -> None:
        status = status.lower()
        if status not in STATUSES:
            raise ValueError(
                f"unknown status {status!r}; expected one of {', '.join(STATUSES)}"
            )
        self.status = status
        self.timeline.append(
            TimelineNote(
                timestamp=timestamp or _now_iso(),
                kind="status",
                text=f"status -> {status}",
            )
        )

    def resolve(self, timestamp: str = "") -> None:
        self.set_status("resolved", timestamp)
        self.timeline[-1].kind = "resolved"

    @property
    def is_open(self) -> bool:
        return self.status != "resolved"

    def to_markdown(self, now: datetime | None = None) -> str:
        lines = [f"# Incident {self.id}: {self.title}", ""]
        lines.append(f"- Status: **{self.status}** | Severity: {self.severity}")
        lines.append(f"- Started: {self.started or 'unknown'}")
        elapsed = self.elapsed_seconds(now)
        if elapsed is not None:
            lines.append(f"- Elapsed: {format_duration(elapsed)}")
        lines.append("")
        lines.append("## Timeline")
        if self.timeline:
            for note in self.timeline:
                lines.append(f"- {note.timestamp} [{note.kind}] {note.text}")
        else:
            lines.append("- _No timeline entries yet._")
        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "severity": self.severity,
            "status": self.status,
            "started": self.started,
            "timeline": [
                {"timestamp": n.timestamp, "kind": n.kind, "text": n.text}
                for n in self.timeline
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Incident":
        return cls(
            id=data["id"],
            title=data.get("title", "untitled incident"),
            severity=data.get("severity", "SEV-3"),
            status=data.get("status", "open"),
            started=data.get("started", ""),
            timeline=[
                TimelineNote(
                    timestamp=raw.get("timestamp", ""),
                    kind=raw.get("kind", "note"),
                    text=raw.get("text", ""),
                )
                for raw in data.get("timeline", [])
            ],
        )


class IncidentStore:
    """JSON-file-backed incident registry."""

    def __init__(self, path: str):
        self.path = path
        self.incidents: dict[str, Incident] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path) as handle:
                raw = json.load(handle)
        except (OSError, ValueError):
            raw = {}
        for item in raw.get("incidents", []):
            incident = Incident.from_dict(item)
            self.incidents[incident.id] = incident

    def save(self) -> None:
        with open(self.path, "w") as handle:
            json.dump(
                {"incidents": [i.to_dict() for i in self.incidents.values()]},
                handle,
                indent=2,
            )

    def _next_id(self) -> str:
        nums = [
            int(i.id.split("-")[1])
            for i in self.incidents.values()
            if i.id.startswith("INC-") and i.id.split("-")[1].isdigit()
        ]
        return f"INC-{(max(nums) + 1) if nums else 1:04d}"

    def start(
        self, title: str, severity: str = "SEV-3", started: str = ""
    ) -> Incident:
        incident = Incident(
            id=self._next_id(),
            title=title,
            severity=severity,
            started=started or _now_iso(),
        )
        incident.timeline.append(
            TimelineNote(
                timestamp=incident.started, kind="opened",
                text=f"opened ({severity})",
            )
        )
        self.incidents[incident.id] = incident
        self.save()
        return incident

    def get(self, incident_id: str) -> Incident:
        try:
            return self.incidents[incident_id.upper()]
        except KeyError:
            raise ValueError(f"unknown incident {incident_id!r}") from None

    def list_open(self) -> list:
        return [i for i in self.incidents.values() if i.is_open]
