"""Secrets rotation audit.

Stale credentials are a quiet breach waiting to happen. This audits
a JSON list of secret metadata — names, owners, last rotation date,
and rotation interval — and flags secrets that are overdue for
rotation or missing an owner. It never reads secret values, only
their rotation metadata.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class SecretRecord:
    name: str
    last_rotated: str = ""  # ISO date, "" when never rotated
    rotation_days: int = 90
    owner: str = ""


@dataclass
class SecretResult:
    record: SecretRecord
    days_since_rotation: int | None  # None when never rotated
    status: str  # ok, due, overdue, unknown


@dataclass
class SecretIssue:
    name: str
    kind: str  # owner, overdue, unknown
    message: str


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip()[:10])
    except (ValueError, AttributeError):
        return None


def check_secrets(records: list, today: date, due_soon_days: int = 7) -> list:
    results = []
    for record in records:
        rotated = _parse_date(record.last_rotated)
        if rotated is None:
            results.append(SecretResult(record, None, "unknown"))
            continue
        days = (today - rotated).days
        if days > record.rotation_days:
            status = "overdue"
        elif days > record.rotation_days - due_soon_days:
            status = "due"
        else:
            status = "ok"
        results.append(SecretResult(record, days, status))
    return results


def audit_issues(results: list) -> list:
    issues = []
    for result in results:
        record = result.record
        if not record.owner:
            issues.append(SecretIssue(record.name, "owner", "no owner team"))
        if result.status == "overdue":
            issues.append(
                SecretIssue(
                    record.name, "overdue",
                    f"overdue by {result.days_since_rotation - record.rotation_days} days",
                )
            )
        elif result.status == "unknown":
            issues.append(
                SecretIssue(record.name, "unknown", "never rotated or bad date")
            )
    return issues


def attention_needed(results: list) -> bool:
    return any(r.status in ("overdue", "unknown") for r in results)


def to_markdown(results: list, issues: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    lines = ["# Secrets rotation audit", ""]
    lines.append(f"- Secrets checked: {len(results)}")
    lines.append(f"- Overdue: {counts.get('overdue', 0)}")
    lines.append(f"- Due soon: {counts.get('due', 0)}")
    lines.append(f"- Unknown: {counts.get('unknown', 0)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Issues found: {len(issues)}")
    lines.append("")
    if not results:
        lines.append("No secrets to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Secrets")
    lines.append("| Secret | Last rotated | Days since | Status |")
    lines.append("| ------ | ------------ | ---------- | ------ |")
    for result in results:
        days = (
            str(result.days_since_rotation)
            if result.days_since_rotation is not None
            else "n/a"
        )
        lines.append(
            f"| {result.record.name} | {result.record.last_rotated or 'never'} "
            f"| {days} | {result.status} |"
        )
    if issues:
        lines.append("")
        lines.append("## Issues")
        lines.append("| Secret | Kind | Message |")
        lines.append("| ------ | ---- | ------- |")
        for issue in issues:
            lines.append(f"| {issue.name} | {issue.kind} | {issue.message} |")
    return "\n".join(lines) + "\n"


def records_from_json(data: list) -> list:
    return [
        SecretRecord(
            name=item.get("name", "unnamed"),
            last_rotated=item.get("last_rotated", ""),
            rotation_days=int(item.get("rotation_days", 90)),
            owner=item.get("owner", ""),
        )
        for item in data
    ]
