"""StatefulSet audit.

A StatefulSet without its governing headless Service loses
the stable network identity its pods depend on, and one
with no volume claim templates is a stateful workload with
no persistent storage at all. This checks a JSON list of
StatefulSets and flags the ones that cannot roll out safely,
update only by hand, or have no owner, so the set is fixed
— or the data protected — before the next rollout stalls.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StatefulSet:
    name: str = "unnamed"
    namespace: str = "default"
    replicas: int = 0
    ready_replicas: int = 0
    service_name: str = ""
    volume_claim_templates: int = 0
    update_strategy: str = "RollingUpdate"
    pod_management_policy: str = "OrderedReady"
    owner: str = ""


@dataclass
class StatefulSetResult:
    stateful_set: StatefulSet
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["no headless service"]


def check_stateful_sets(sets: list) -> list:
    results = []
    for item in sets:
        issues = []
        blocked = False
        if not item.service_name:
            issues.append("no headless service")
            blocked = True
        if item.volume_claim_templates == 0:
            issues.append("no volume claim templates")
            blocked = True
        if item.replicas > 0 and item.ready_replicas < item.replicas:
            issues.append("not fully ready")
            blocked = True
        if item.update_strategy == "OnDelete":
            issues.append("manual updates only")
        if item.pod_management_policy == "Parallel":
            issues.append("parallel pod management")
        if not item.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(StatefulSetResult(item, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# StatefulSet audit", ""]
    lines.append(f"- StatefulSets checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No StatefulSets to check.")
        return "\n".join(lines) + "\n"
    lines.append("## StatefulSets")
    lines.append(
        "| Namespace | StatefulSet | Replicas | Ready | Service "
        "| Volume claims | Update strategy | Pod management "
        "| Owner | Verdict | Issues |"
    )
    lines.append(
        "| --------- | ----------- | -------- | ----- | ------- "
        "| ------------- | --------------- | -------------- "
        "| ----- | ------- | ------ |"
    )
    for result in sorted(
        results, key=lambda r: (r.stateful_set.namespace, r.stateful_set.name)
    ):
        item = result.stateful_set
        service = item.service_name or "—"
        owner = item.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {item.namespace} | {item.name} | {item.replicas} "
            f"| {item.ready_replicas} | {service} "
            f"| {item.volume_claim_templates} | {item.update_strategy} "
            f"| {item.pod_management_policy} | {owner} "
            f"| {result.verdict} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def stateful_sets_from_json(data: list) -> list:
    return [
        StatefulSet(
            name=item.get("name", "unnamed"),
            namespace=item.get("namespace", "default"),
            replicas=int(item.get("replicas", 0)),
            ready_replicas=int(item.get("ready_replicas", 0)),
            service_name=item.get("service_name", ""),
            volume_claim_templates=int(
                item.get("volume_claim_templates", 0)
            ),
            update_strategy=item.get(
                "update_strategy", "RollingUpdate"
            ),
            pod_management_policy=item.get(
                "pod_management_policy", "OrderedReady"
            ),
            owner=item.get("owner", ""),
        )
        for item in data
    ]
