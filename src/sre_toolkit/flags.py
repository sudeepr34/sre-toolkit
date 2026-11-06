"""Feature flag audit.

Flags pile up: half the fleet is enabled-and-forgotten, and nobody
remembers who owns them. This audits a JSON list of flags for missing
owners and stale enabled flags (unused longer than a threshold), so the
flag list stays small enough to reason about in an incident.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class Flag:
    name: str
    enabled: bool = False
    owner: str = ""
    last_used: str = ""  # ISO date, "" when never used
    created: str = ""  # ISO date


@dataclass
class FlagIssue:
    name: str
    kind: str  # owner, stale
    message: str


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip()[:10])
    except (ValueError, AttributeError):
        return None


def audit_flags(flags: list, today: date, stale_days: int = 90) -> list:
    issues = []
    for flag in flags:
        if not flag.owner:
            issues.append(FlagIssue(flag.name, "owner", "no owner team"))
        if not flag.enabled:
            continue
        reference = _parse_date(flag.last_used) or _parse_date(flag.created)
        if reference is None:
            issues.append(
                FlagIssue(flag.name, "stale", "enabled, no usage or creation date")
            )
        elif (today - reference).days > stale_days:
            issues.append(
                FlagIssue(
                    flag.name, "stale",
                    f"enabled, unused for {(today - reference).days} days",
                )
            )
    return issues


def to_markdown(flags: list, issues: list) -> str:
    lines = ["# Feature flag audit", ""]
    lines.append(f"- Flags checked: {len(flags)}")
    lines.append(f"- Issues found: {len(issues)}")
    lines.append(f"- Enabled: {sum(1 for f in flags if f.enabled)}")
    lines.append("")
    if not issues:
        lines.append("Flags clean: every flag has an owner and none is stale.")
        return "\n".join(lines) + "\n"
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.kind] = counts.get(issue.kind, 0) + 1
    lines.append("## Issues by kind")
    for kind, count in sorted(counts.items()):
        lines.append(f"- {kind}: {count}")
    lines.append("")
    lines.append("## Issues")
    lines.append("| Flag | Kind | Message |")
    lines.append("| ---- | ---- | ------- |")
    for issue in issues:
        lines.append(f"| {issue.name} | {issue.kind} | {issue.message} |")
    return "\n".join(lines) + "\n"


def flags_from_json(data: list) -> list:
    return [
        Flag(
            name=item.get("name", "unnamed"),
            enabled=bool(item.get("enabled", False)),
            owner=item.get("owner", ""),
            last_used=item.get("last_used", ""),
            created=item.get("created", ""),
        )
        for item in data
    ]
