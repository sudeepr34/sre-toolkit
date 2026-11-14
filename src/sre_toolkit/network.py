"""NetworkPolicy audit.

A namespace with workloads but no NetworkPolicy is flat — any pod can
reach any other pod. This checks a JSON list of workloads against
their NetworkPolicies and flags the unsegmented ones, so the policy
is written — or the allow-all rule narrowed — before the next
lateral-movement incident.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Workload:
    namespace: str = "default"
    workload: str = "unnamed"
    pod_selector: str = ""
    has_policy: bool = False
    ingress: list = field(default_factory=list)  # CIDRs allowed in
    egress: list = field(default_factory=list)  # CIDRs allowed out
    default_deny: bool = False
    owner: str = ""


@dataclass
class NetworkResult:
    workload: Workload
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["no NetworkPolicy"]


def check_network(workloads: list) -> list:
    results = []
    for workload in workloads:
        issues = []
        blocked = False
        if not workload.has_policy:
            issues.append("no NetworkPolicy")
            blocked = True
        if "0.0.0.0/0" in workload.ingress:
            issues.append("allows all ingress (0.0.0.0/0)")
            blocked = True
        if not workload.default_deny and workload.has_policy:
            issues.append("no default-deny policy")
        if "0.0.0.0/0" in workload.egress:
            issues.append("allows all egress (0.0.0.0/0)")
        if not workload.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(NetworkResult(workload, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# NetworkPolicy audit", ""]
    lines.append(f"- Workloads checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No workloads to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Workloads")
    lines.append("| Namespace | Workload | Policy | Default deny | Owner | Verdict | Issues |")
    lines.append("| --------- | -------- | ------ | ------------ | ----- | ------- | ------ |")
    for result in sorted(
        results, key=lambda r: (r.workload.namespace, r.workload.workload)
    ):
        workload = result.workload
        policy = "yes" if workload.has_policy else "no"
        deny = "yes" if workload.default_deny else "no"
        owner = workload.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {workload.namespace} | {workload.workload} | {policy} "
            f"| {deny} | {owner} | {result.verdict} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def workloads_from_json(data: list) -> list:
    return [
        Workload(
            namespace=item.get("namespace", "default"),
            workload=item.get("workload", "unnamed"),
            pod_selector=item.get("pod_selector", ""),
            has_policy=bool(item.get("has_policy", False)),
            ingress=list(item.get("ingress", [])),
            egress=list(item.get("egress", [])),
            default_deny=bool(item.get("default_deny", False)),
            owner=item.get("owner", ""),
        )
        for item in data
    ]
