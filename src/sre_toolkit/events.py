"""Event correlation.

A single alert is noise; five alerts on one service in ten minutes is
an incident, and the same ten minutes lighting up two services is a
shared cause. This correlates a JSON list of events: it finds bursts
per service and windows where several services fired together, so the
triage starts from the cluster instead of the loudest single alert.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class Event:
    service: str
    timestamp: str  # ISO datetime
    severity: str = "info"
    message: str = ""


@dataclass
class Burst:
    service: str
    window_start: datetime
    count: int


@dataclass
class Correlated:
    window_start: datetime
    services: list


def _parse_timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        return None


def _window_start(moment: datetime, window_minutes: int) -> datetime:
    floored = moment.replace(second=0, microsecond=0)
    return floored - timedelta(minutes=floored.minute % window_minutes)


def find_bursts(
    events: list, window_minutes: int = 15, threshold: int = 5
) -> list:
    """Per-service bursts: >= threshold events inside a sliding window."""
    by_service: dict[str, list] = {}
    for event in events:
        moment = _parse_timestamp(event.timestamp)
        if moment is not None:
            by_service.setdefault(event.service, []).append(moment)
    bursts = []
    window = timedelta(minutes=window_minutes)
    for service, moments in sorted(by_service.items()):
        moments.sort()
        start = 0
        while start < len(moments):
            end = start
            while end < len(moments) and moments[end] - moments[start] < window:
                end += 1
            if end - start >= threshold:
                bursts.append(Burst(service, moments[start], end - start))
                start = end
            else:
                start += 1
    return bursts


def find_correlated(events: list, window_minutes: int = 15) -> list:
    """Windows where two or more services fired together."""
    buckets: dict[datetime, set] = {}
    for event in events:
        moment = _parse_timestamp(event.timestamp)
        if moment is not None:
            buckets.setdefault(_window_start(moment, window_minutes), set()).add(
                event.service
            )
    return [
        Correlated(start, sorted(services))
        for start, services in sorted(buckets.items())
        if len(services) >= 2
    ]


def to_markdown(bursts: list, correlated: list, window_minutes: int) -> str:
    lines = ["# Event correlation", ""]
    lines.append(f"- Window: {window_minutes} minutes")
    lines.append(f"- Bursts found: {len(bursts)}")
    lines.append(f"- Correlated windows: {len(correlated)}")
    lines.append("")
    if bursts:
        lines.append("## Bursts")
        lines.append("| Service | Window start | Events |")
        lines.append("| ------- | ------------ | ------ |")
        for burst in bursts:
            lines.append(
                f"| {burst.service} | {burst.window_start.isoformat()} "
                f"| {burst.count} |"
            )
        lines.append("")
    if correlated:
        lines.append("## Correlated windows")
        lines.append("| Window start | Services |")
        lines.append("| ------------ | -------- |")
        for group in correlated:
            lines.append(
                f"| {group.window_start.isoformat()} | {', '.join(group.services)} |"
            )
        lines.append("")
    if not bursts and not correlated:
        lines.append("No bursts or correlated windows found.")
    return "\n".join(lines) + "\n"


def events_from_json(data: list) -> list:
    return [
        Event(
            service=item.get("service", "unnamed"),
            timestamp=item.get("timestamp", ""),
            severity=item.get("severity", "info"),
            message=item.get("message", ""),
        )
        for item in data
    ]
