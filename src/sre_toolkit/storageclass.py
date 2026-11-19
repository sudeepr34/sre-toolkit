"""StorageClass audit.

A cluster with no default StorageClass leaves every PVC
without an explicit class pending forever, and a Delete
reclaim policy silently wipes stateful data when the claim
goes. This checks a JSON list of StorageClasses and flags
the ones that are missing a provisioner, use Delete reclaim,
duplicate the default, or have no owner, so the class is
fixed — or the data protected — before the next PVC stalls.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StorageClass:
    name: str = "unnamed"
    provisioner: str = ""
    reclaim_policy: str = "Delete"
    is_default: bool = False
    owner: str = ""


@dataclass
class StorageClassResult:
    storage_class: StorageClass
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["delete reclaim policy"]


def check_storage_classes(classes: list) -> list:
    defaults = sum(1 for item in classes if item.is_default)
    has_default = defaults > 0
    results = []
    for item in classes:
        issues = []
        blocked = False
        if not item.provisioner:
            issues.append("no provisioner")
            blocked = True
        if item.reclaim_policy == "Delete":
            issues.append("delete reclaim policy")
        if item.provisioner == "kubernetes.io/no-provisioner":
            issues.append("manual provisioning only")
        if defaults > 1 and item.is_default:
            issues.append("duplicate default class")
        if not has_default:
            issues.append("no default storage class")
        if not item.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(StorageClassResult(item, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# StorageClass audit", ""]
    lines.append(f"- StorageClasses checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No StorageClasses to check.")
        return "\n".join(lines) + "\n"
    lines.append("## StorageClasses")
    lines.append(
        "| Class | Provisioner | Reclaim policy | Default "
        "| Owner | Verdict | Issues |"
    )
    lines.append(
        "| ----- | ----------- | -------------- | ------- "
        "| ----- | ------- | ------ |"
    )
    for result in sorted(
        results, key=lambda r: r.storage_class.name
    ):
        item = result.storage_class
        provisioner = item.provisioner or "—"
        default = "yes" if item.is_default else "no"
        owner = item.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {item.name} | {provisioner} | {item.reclaim_policy} "
            f"| {default} | {owner} | {result.verdict} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def storage_classes_from_json(data: list) -> list:
    return [
        StorageClass(
            name=item.get("name", "unnamed"),
            provisioner=item.get("provisioner", ""),
            reclaim_policy=item.get("reclaim_policy", "Delete"),
            is_default=bool(item.get("is_default", False)),
            owner=item.get("owner", ""),
        )
        for item in data
    ]
