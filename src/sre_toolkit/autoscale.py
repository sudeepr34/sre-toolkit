"""HPA autoscale audit.

A HorizontalPodAutoscaler that cannot scale is a silent capacity
ceiling: traffic grows, replicas stay put, and the service sheds
load at the worst moment. This checks a JSON list of workloads
against their HPA configuration and flags the ones that cannot
scale, have no scaling signal, or are already running hot, so the
HPA is fixed — or the ceiling raised — before the next traffic
spike.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AutoscaleWorkload:
    deployment: str = "unnamed"
    namespace: str = "default"
    has_hpa: bool = False
    min_replicas: int = 1
    max_replicas: int = 1
    current_replicas: int = 0
    target_cpu_pct: float | None = None
    current_cpu_pct: float | None = None
    metric: str = ""
    owner: str = ""


@dataclass
class AutoscaleResult:
    workload: AutoscaleWorkload
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["no HPA"]


def check_autoscale(workloads: list) -> list:
    results = []
    for workload in workloads:
        issues = []
        blocked = False
        if not workload.has_hpa:
            issues.append("no HPA")
            blocked = True
        if workload.min_replicas > workload.max_replicas:
            issues.append("min replicas above max replicas")
            blocked = True
        if workload.min_replicas == workload.max_replicas:
            issues.append("min equals max (cannot scale)")
            blocked = True
        if (
            workload.current_replicas > 0
            and workload.max_replicas <= workload.current_replicas
        ):
            issues.append("max replicas at or below current replicas")
            blocked = True
        if workload.target_cpu_pct is None:
            issues.append("no target CPU %")
        if not workload.metric:
            issues.append("no metric")
        if (
            workload.target_cpu_pct is not None
            and workload.current_cpu_pct is not None
            and workload.current_cpu_pct > workload.target_cpu_pct
        ):
            issues.append("current CPU above target")
        if not workload.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(AutoscaleResult(workload, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# HPA autoscale audit", ""]
    lines.append(f"- Workloads checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No workloads to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Workloads")
    lines.append(
        "| Namespace | Deployment | HPA | Min | Max | Target CPU "
        "| Current CPU | Owner | Verdict | Issues |"
    )
    lines.append(
        "| --------- | ---------- | --- | --- | --- | ---------- "
        "| ----------- | ----- | ------- | ------ |"
    )
    for result in sorted(
        results, key=lambda r: (r.workload.namespace, r.workload.deployment)
    ):
        workload = result.workload
        hpa = "yes" if workload.has_hpa else "no"
        target = (
            f"{workload.target_cpu_pct:g}%"
            if workload.target_cpu_pct is not None
            else "—"
        )
        current = (
            f"{workload.current_cpu_pct:g}%"
            if workload.current_cpu_pct is not None
            else "—"
        )
        owner = workload.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {workload.namespace} | {workload.deployment} | {hpa} "
            f"| {workload.min_replicas} | {workload.max_replicas} "
            f"| {target} | {current} | {owner} | {result.verdict} "
            f"| {issues} |"
        )
    return "\n".join(lines) + "\n"


def workloads_from_json(data: list) -> list:
    workloads = []
    for item in data:
        target = item.get("target_cpu_pct")
        current = item.get("current_cpu_pct")
        workloads.append(
            AutoscaleWorkload(
                deployment=item.get("deployment", "unnamed"),
                namespace=item.get("namespace", "default"),
                has_hpa=bool(item.get("has_hpa", False)),
                min_replicas=int(item.get("min_replicas", 1)),
                max_replicas=int(item.get("max_replicas", 1)),
                current_replicas=int(item.get("current_replicas", 0)),
                target_cpu_pct=None if target is None else float(target),
                current_cpu_pct=None if current is None else float(current),
                metric=item.get("metric", ""),
                owner=item.get("owner", ""),
            )
        )
    return workloads
