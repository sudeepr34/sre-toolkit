"""DORA metrics: deployment frequency and change failure rate.

Two of the four DORA metrics, computed from a JSON list of deploy
records over a window: how often the team ships, and how often a
change fails. The numbers a planning review actually argues about.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class DeployRecord:
    service: str
    timestamp: str  # ISO date or datetime
    status: str = "success"  # success, failed
    lead_time_hours: float | None = None


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip()[:10])
    except (ValueError, AttributeError):
        return None


def in_window(records: list, start: date, end: date) -> list:
    """Records whose timestamp falls inside [start, end]."""
    kept = []
    for record in records:
        day = _parse_date(record.timestamp)
        if day is not None and start <= day <= end:
            kept.append(record)
    return kept


def deployment_frequency(records: list, days: int) -> float:
    """Deploys per week over the window."""
    if days <= 0:
        return 0.0
    return len(records) / days * 7


def change_failure_rate(records: list) -> float | None:
    """Failed deploys as a share of all deploys; None when there are none."""
    if not records:
        return None
    failed = sum(1 for r in records if r.status.lower() == "failed")
    return failed / len(records) * 100


def mean_lead_time_hours(records: list) -> float | None:
    """Mean lead time over records that report one; None when none do."""
    times = [r.lead_time_hours for r in records if r.lead_time_hours is not None]
    if not times:
        return None
    return sum(times) / len(times)


def per_service(records: list) -> list:
    """(service, deploys, failures) per service, most deploys first."""
    totals: dict[str, list] = {}
    for record in records:
        entry = totals.setdefault(record.service, [0, 0])
        entry[0] += 1
        if record.status.lower() == "failed":
            entry[1] += 1
    return sorted(
        ((service, deploys, failed) for service, (deploys, failed) in totals.items()),
        key=lambda item: item[1],
        reverse=True,
    )


def to_markdown(records: list, start: date, end: date) -> str:
    days = (end - start).days + 1
    lines = ["# DORA metrics", ""]
    lines.append(f"- Window: {start.isoformat()} to {end.isoformat()} ({days} days)")
    lines.append(f"- Deploys: {len(records)}")
    lines.append(f"- Deployment frequency: {deployment_frequency(records, days):.2f} per week")
    rate = change_failure_rate(records)
    lines.append(
        "- Change failure rate: "
        + (f"{rate:.1f}%" if rate is not None else "n/a (no deploys)")
    )
    lead = mean_lead_time_hours(records)
    if lead is not None:
        lines.append(f"- Mean lead time: {lead:.1f} hours")
    lines.append("")
    lines.append("## Per service")
    lines.append("| Service | Deploys | Failures |")
    lines.append("| ------- | ------- | -------- |")
    for service, deploys, failed in per_service(records):
        lines.append(f"| {service} | {deploys} | {failed} |")
    if not records:
        lines.append("| _none_ | 0 | 0 |")
    return "\n".join(lines) + "\n"


def records_from_json(data: list) -> list:
    return [
        DeployRecord(
            service=item.get("service", "unnamed"),
            timestamp=item.get("timestamp", ""),
            status=item.get("status", "success"),
            lead_time_hours=(
                float(item["lead_time_hours"])
                if item.get("lead_time_hours") is not None else None
            ),
        )
        for item in data
    ]
