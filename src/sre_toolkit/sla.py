"""SLA availability compliance.

An SLO says how good you should be; an SLA says what you owe when
you're not. This checks each service's measured availability against
its SLA target over a window and reports the error budget left in
minutes, so a breach is visible before the contract is.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SLARecord:
    service: str
    uptime_pct: float
    target_pct: float  # e.g. 99.9


@dataclass
class SLAResult:
    record: SLARecord
    budget_minutes: float  # negative when breached
    compliant: bool


def window_minutes(window_days: int) -> float:
    return window_days * 24 * 60


def error_budget_minutes(
    uptime_pct: float, target_pct: float, window_days: int = 30
) -> float:
    """Minutes of availability above (or below) the target over the window."""
    return (uptime_pct - target_pct) / 100 * window_minutes(window_days)


def check_sla(records: list, window_days: int = 30) -> list:
    results = []
    for record in records:
        budget = error_budget_minutes(
            record.uptime_pct, record.target_pct, window_days
        )
        results.append(SLAResult(record, budget, budget >= 0))
    return results


def to_markdown(results: list, window_days: int = 30) -> str:
    breached = [r for r in results if not r.compliant]
    lines = ["# SLA availability check", ""]
    lines.append(f"- Window: {window_days} days")
    lines.append(f"- Services checked: {len(results)}")
    lines.append(f"- Compliant: {len(results) - len(breached)}")
    lines.append(f"- Breached: {len(breached)}")
    lines.append("")
    if not results:
        lines.append("No services to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Services")
    lines.append("| Service | Uptime | Target | Budget left (min) | Status |")
    lines.append("| ------- | ------ | ------ | ----------------- | ------ |")
    for result in results:
        record = result.record
        status = "compliant" if result.compliant else "BREACHED"
        lines.append(
            f"| {record.service} | {record.uptime_pct:.3f}% "
            f"| {record.target_pct:.3f}% | {result.budget_minutes:.1f} | {status} |"
        )
    return "\n".join(lines) + "\n"


def records_from_json(data: list) -> list:
    return [
        SLARecord(
            service=item.get("service", "unnamed"),
            uptime_pct=float(item.get("uptime_pct", 0.0)),
            target_pct=float(item.get("target_pct", 0.0)),
        )
        for item in data
    ]
