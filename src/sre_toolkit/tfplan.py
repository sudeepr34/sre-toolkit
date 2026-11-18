"""Terraform plan audit.

A `terraform apply` that destroys a database or replaces a bucket
is a data-loss event wearing a plan's clothing. This checks a JSON
list of planned changes and flags the ones that must not go ahead
without approval, so the plan is gated — or the change reworked —
before apply runs.
"""
from __future__ import annotations

from dataclasses import dataclass

STATEFUL_KEYWORDS = (
    "db",
    "database",
    "rds",
    "sql",
    "dynamodb",
    "redis",
    "elasticache",
    "bucket",
    "s3",
    "volume",
    "ebs",
    "efs",
    "disk",
)

SENSITIVE_KEYWORDS = (
    ("iam", "IAM resource"),
    ("security_group", "security group"),
    ("kms", "KMS resource"),
    ("vpc", "network resource"),
    ("subnet", "network resource"),
    ("route", "network resource"),
    ("nat_gateway", "network resource"),
    ("internet_gateway", "network resource"),
    ("network", "network resource"),
)

ACTIONS = ("create", "update", "destroy", "replace", "no-op")


@dataclass
class PlannedChange:
    address: str = "unnamed"
    resource_type: str = ""
    action: str = "no-op"
    owner: str = ""
    approved: bool = False


@dataclass
class PlanResult:
    change: PlannedChange
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["destroy of stateful resource"]


def _is_stateful(resource_type: str) -> bool:
    lowered = resource_type.lower()
    return any(keyword in lowered for keyword in STATEFUL_KEYWORDS)


def _sensitive_label(resource_type: str) -> str | None:
    lowered = resource_type.lower()
    for keyword, label in SENSITIVE_KEYWORDS:
        if keyword in lowered:
            return label
    return None


def check_plan(changes: list) -> list:
    results = []
    for change in changes:
        issues = []
        blocked = False
        action = change.action.lower()
        if action in ("destroy", "replace") and _is_stateful(
            change.resource_type
        ):
            issues.append(f"{action} of stateful resource")
            blocked = True
        if action in ("destroy", "replace") and not change.approved:
            issues.append(f"{action} without approval")
            blocked = True
        if action == "replace":
            issues.append("replace")
        if action == "update":
            label = _sensitive_label(change.resource_type)
            if label is not None:
                issues.append(f"update to {label}")
        if action not in ACTIONS:
            issues.append("unknown action")
        if not change.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(PlanResult(change, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# Terraform plan audit", ""]
    lines.append(f"- Changes checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No changes to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Changes")
    lines.append(
        "| Address | Type | Action | Approved | Owner | Verdict | Issues |"
    )
    lines.append(
        "| ------- | ---- | ------ | -------- | ----- | ------- | ------ |"
    )
    for result in sorted(results, key=lambda r: r.change.address):
        change = result.change
        approved = "yes" if change.approved else "no"
        owner = change.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {change.address} | {change.resource_type} "
            f"| {change.action} | {approved} | {owner} "
            f"| {result.verdict} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def changes_from_json(data: list) -> list:
    changes = []
    for item in data:
        changes.append(
            PlannedChange(
                address=item.get("address", "unnamed"),
                resource_type=item.get("type", ""),
                action=item.get("action", "no-op"),
                owner=item.get("owner", ""),
                approved=bool(item.get("approved", False)),
            )
        )
    return changes
