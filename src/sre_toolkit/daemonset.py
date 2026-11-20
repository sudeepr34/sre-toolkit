"""DaemonSet audit.

A DaemonSet that is not fully ready leaves some nodes without
the agent it is supposed to run everywhere — logging, monitoring,
or networking — and a misscheduled pod means a node the
scheduler could not place it on at all. This checks a JSON list
of DaemonSets and flags the ones that are degraded, update only
by hand, or have no owner, so the gap is fixed before the next
node joins unprotected.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DaemonSet:
    name: str = "unnamed"
    namespace: str = "default"
    desired: int = 0
    ready: int = 0
    misscheduled: int = 0
    update_strategy: str = "RollingUpdate"
    owner: str = ""


@dataclass
class DaemonSetResult:
    daemon_set: DaemonSet
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["not fully ready"]


def check_daemon_sets(sets: list) -> list:
    results = []
    for item in sets:
        issues = []
        blocked = False
        if item.desired > 0 and item.ready < item.desired:
            issues.append("not fully ready")
            blocked = True
        if item.misscheduled > 0:
            issues.append("pods misscheduled")
            blocked = True
        if item.update_strategy == "OnDelete":
            issues.append("manual updates only")
        if not item.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(DaemonSetResult(item, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# DaemonSet audit", ""]
    lines.append(f"- DaemonSets checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No DaemonSets to check.")
        return "\n".join(lines) + "\n"
    lines.append("## DaemonSets")
    lines.append(
        "| Namespace | DaemonSet | Desired | Ready | Misscheduled "
        "| Update strategy | Owner | Verdict | Issues |"
    )
    lines.append(
        "| --------- | --------- | ------- | ----- | ------------ "
        "| --------------- | ----- | ------- | ------ |"
    )
    for result in sorted(
        results, key=lambda r: (r.daemon_set.namespace, r.daemon_set.name)
    ):
        item = result.daemon_set
        owner = item.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {item.namespace} | {item.name} | {item.desired} "
            f"| {item.ready} | {item.misscheduled} "
            f"| {item.update_strategy} | {owner} "
            f"| {result.verdict} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def daemon_sets_from_json(data: list) -> list:
    return [
        DaemonSet(
            name=item.get("name", "unnamed"),
            namespace=item.get("namespace", "default"),
            desired=int(item.get("desired", 0)),
            ready=int(item.get("ready", 0)),
            misscheduled=int(item.get("misscheduled", 0)),
            update_strategy=item.get(
                "update_strategy", "RollingUpdate"
            ),
            owner=item.get("owner", ""),
        )
        for item in data
    ]
