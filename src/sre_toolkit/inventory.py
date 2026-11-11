"""Host inventory audit.

A host nobody owns and nobody patched is an incident waiting for a
date. This audits a JSON list of hosts for missing owners, unknown
environments, and stale or missing patches, so the forgotten boxes get
named before an attacker does it for you.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

KNOWN_ENVIRONMENTS = {"prod", "staging", "dev"}


@dataclass
class Host:
    name: str
    owner: str = ""
    environment: str = ""
    patched: bool = False
    last_patched: str = ""  # ISO date


@dataclass
class HostIssue:
    host: Host
    issues: list  # e.g. ["missing owner", "unpatched"]


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip()[:10])
    except (ValueError, AttributeError):
        return None


def check_hosts(hosts: list, today: date, patch_max_days: int = 30) -> list:
    results = []
    for host in hosts:
        issues = []
        if not host.owner.strip():
            issues.append("missing owner")
        if host.environment.lower() not in KNOWN_ENVIRONMENTS:
            issues.append("unknown environment")
        patched_date = _parse_date(host.last_patched)
        if not host.patched:
            issues.append("unpatched")
        elif patched_date is None:
            issues.append("unknown patch date")
        elif (today - patched_date).days > patch_max_days:
            issues.append("patch stale")
        results.append(HostIssue(host, issues))
    return results


def to_markdown(results: list) -> str:
    with_issues = [r for r in results if r.issues]
    lines = ["# Host inventory audit", ""]
    lines.append(f"- Hosts checked: {len(results)}")
    lines.append(f"- Hosts with issues: {len(with_issues)}")
    lines.append("")
    if not with_issues:
        lines.append("Clean: every host has an owner, a known environment, and a fresh patch.")
        return "\n".join(lines) + "\n"
    lines.append("## Issues")
    lines.append("| Host | Environment | Owner | Issues |")
    lines.append("| ---- | ----------- | ----- | ------ |")
    for result in with_issues:
        lines.append(
            f"| {result.host.name} | {result.host.environment or '—'} "
            f"| {result.host.owner or '—'} | {', '.join(result.issues)} |"
        )
    return "\n".join(lines) + "\n"


def hosts_from_json(data: list) -> list:
    return [
        Host(
            name=item.get("name", "unnamed"),
            owner=item.get("owner", ""),
            environment=item.get("environment", ""),
            patched=bool(item.get("patched", False)),
            last_patched=item.get("last_patched", ""),
        )
        for item in data
    ]
