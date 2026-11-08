"""Rollback readiness check.

A deploy you can't roll back is a deploy you can't undo. This checks
a JSON list of recent deploys and flags the ones missing a previous
version to roll back to, a rollback runbook, or a tested rollback, so
the gap is found in review instead of in the middle of an incident.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeployRecord:
    service: str
    version: str
    previous_version: str = ""
    rollback_runbook: str = ""
    rollback_tested: bool = False


@dataclass
class RollbackIssue:
    service: str
    version: str
    kind: str  # previous_version, runbook, untested
    message: str


def check_rollback(deploys: list) -> list:
    issues = []
    for deploy in deploys:
        if not deploy.previous_version:
            issues.append(
                RollbackIssue(
                    deploy.service, deploy.version,
                    "previous_version", "no previous version to roll back to",
                )
            )
        if not deploy.rollback_runbook:
            issues.append(
                RollbackIssue(
                    deploy.service, deploy.version,
                    "runbook", "no rollback runbook",
                )
            )
        if not deploy.rollback_tested:
            issues.append(
                RollbackIssue(
                    deploy.service, deploy.version,
                    "untested", "rollback never tested",
                )
            )
    return issues


def ready_count(deploys: list, issues: list) -> int:
    flagged = {
        (issue.service, issue.version) for issue in issues
    }
    return sum(
        1
        for deploy in deploys
        if (deploy.service, deploy.version) not in flagged
    )


def to_markdown(deploys: list, issues: list) -> str:
    lines = ["# Rollback readiness", ""]
    lines.append(f"- Deploys checked: {len(deploys)}")
    lines.append(f"- Ready to roll back: {ready_count(deploys, issues)}")
    lines.append(f"- Issues found: {len(issues)}")
    lines.append("")
    if not issues:
        lines.append(
            "All deploys are rollback-ready: previous version, runbook, "
            "and a tested rollback."
        )
        return "\n".join(lines) + "\n"
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.kind] = counts.get(issue.kind, 0) + 1
    lines.append("## Issues by kind")
    for kind, count in sorted(counts.items()):
        lines.append(f"- {kind}: {count}")
    lines.append("")
    lines.append("## Issues")
    lines.append("| Service | Version | Kind | Message |")
    lines.append("| ------- | ------- | ---- | ------- |")
    for issue in issues:
        lines.append(
            f"| {issue.service} | {issue.version} | {issue.kind} | {issue.message} |"
        )
    return "\n".join(lines) + "\n"


def records_from_json(data: list) -> list:
    return [
        DeployRecord(
            service=item.get("service", "unnamed"),
            version=item.get("version", ""),
            previous_version=item.get("previous_version", ""),
            rollback_runbook=item.get("rollback_runbook", ""),
            rollback_tested=bool(item.get("rollback_tested", False)),
        )
        for item in data
    ]
