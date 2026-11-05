"""Service catalog audit.

A service catalog is only useful if every entry is owned, tiered, and
linked to a runbook. This audits a JSON list of services and flags
missing owners, missing runbooks, and unknown or missing tiers, so the
catalog stays trustworthy enough to page from.
"""
from __future__ import annotations

from dataclasses import dataclass

VALID_TIERS = ("critical", "high", "standard", "low")


@dataclass
class ServiceEntry:
    name: str
    owner: str = ""
    tier: str = ""
    runbook: str = ""


@dataclass
class CatalogIssue:
    service: str
    kind: str  # owner, tier, runbook
    message: str


def audit_services(services: list) -> list:
    issues = []
    for service in services:
        if not service.owner:
            issues.append(CatalogIssue(service.name, "owner", "no owner team"))
        if not service.tier:
            issues.append(CatalogIssue(service.name, "tier", "no tier set"))
        elif service.tier.lower() not in VALID_TIERS:
            issues.append(
                CatalogIssue(
                    service.name, "tier", f"unknown tier {service.tier!r}"
                )
            )
        if not service.runbook:
            issues.append(CatalogIssue(service.name, "runbook", "no runbook link"))
    return issues


def to_markdown(services: list, issues: list) -> str:
    lines = ["# Service catalog audit", ""]
    lines.append(f"- Services checked: {len(services)}")
    lines.append(f"- Issues found: {len(issues)}")
    lines.append("")
    if not issues:
        lines.append("Catalog clean: every service has an owner, tier, and runbook.")
        return "\n".join(lines) + "\n"
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.kind] = counts.get(issue.kind, 0) + 1
    lines.append("## Issues by kind")
    for kind, count in sorted(counts.items()):
        lines.append(f"- {kind}: {count}")
    lines.append("")
    lines.append("## Issues")
    lines.append("| Service | Kind | Message |")
    lines.append("| ------- | ---- | ------- |")
    for issue in issues:
        lines.append(f"| {issue.service} | {issue.kind} | {issue.message} |")
    return "\n".join(lines) + "\n"


def services_from_json(data: list) -> list:
    return [
        ServiceEntry(
            name=item.get("name", "unnamed"),
            owner=item.get("owner", ""),
            tier=item.get("tier", ""),
            runbook=item.get("runbook", ""),
        )
        for item in data
    ]
