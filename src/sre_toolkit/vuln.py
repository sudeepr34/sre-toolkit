"""Vulnerability triage.

Findings are only useful if the old ones get fixed. This triages a
JSON list of vulnerability findings against per-severity fix SLAs —
critical 7 days, high 30, medium 90, low 180 — and flags overdue and
due-soon findings, so the oldest criticals can't hide at the bottom
of the list.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

SEVERITY_SLA_DAYS = {
    "critical": 7,
    "high": 30,
    "medium": 90,
    "low": 180,
}


@dataclass
class Finding:
    id: str
    severity: str  # critical, high, medium, low
    service: str
    discovered: str  # ISO date
    sla_days: int | None = None  # None -> default for the severity


@dataclass
class VulnResult:
    finding: Finding
    days_open: int | None  # None when the discovered date won't parse
    sla_days: int
    status: str  # ok, due, overdue, unknown


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip()[:10])
    except (ValueError, AttributeError):
        return None


def sla_for(severity: str) -> int:
    return SEVERITY_SLA_DAYS.get(severity.lower(), 90)


def check_vulns(findings: list, today: date, due_soon_days: int = 7) -> list:
    results = []
    for finding in findings:
        sla = finding.sla_days if finding.sla_days is not None else sla_for(finding.severity)
        discovered = _parse_date(finding.discovered)
        if discovered is None:
            results.append(VulnResult(finding, None, sla, "unknown"))
            continue
        days = (today - discovered).days
        if days > sla:
            status = "overdue"
        elif days > sla - due_soon_days:
            status = "due"
        else:
            status = "ok"
        results.append(VulnResult(finding, days, sla, status))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    lines = ["# Vulnerability triage", ""]
    lines.append(f"- Findings checked: {len(results)}")
    lines.append(f"- Overdue: {counts.get('overdue', 0)}")
    lines.append(f"- Due soon: {counts.get('due', 0)}")
    lines.append(f"- Unknown: {counts.get('unknown', 0)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append("")
    if not results:
        lines.append("No findings to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Findings")
    lines.append("| ID | Severity | Service | Days open | SLA | Status |")
    lines.append("| -- | -------- | ------- | --------- | --- | ------ |")
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    for result in sorted(
        results,
        key=lambda r: (severity_rank.get(r.finding.severity.lower(), 4),
                       -(r.days_open or 0)),
    ):
        days = str(result.days_open) if result.days_open is not None else "n/a"
        lines.append(
            f"| {result.finding.id} | {result.finding.severity} "
            f"| {result.finding.service} | {days} | {result.sla_days} "
            f"| {result.status} |"
        )
    return "\n".join(lines) + "\n"


def findings_from_json(data: list) -> list:
    return [
        Finding(
            id=item.get("id", "unnamed"),
            severity=item.get("severity", "medium"),
            service=item.get("service", "unnamed"),
            discovered=item.get("discovered", ""),
            sla_days=(
                int(item["sla_days"])
                if item.get("sla_days") is not None else None
            ),
        )
        for item in data
    ]
