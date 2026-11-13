"""Namespace resource quota check.

A namespace creeping up to its quota will start refusing new pods at
the worst possible moment. This checks a JSON list of namespaces
against their CPU and memory quotas and flags the ones over the
threshold, so the quota is raised — or the workload moved — before
the scheduler starts saying no.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Namespace:
    name: str
    cpu_limit: float = 0.0
    cpu_used: float = 0.0
    memory_limit: float = 0.0  # GiB
    memory_used: float = 0.0  # GiB


@dataclass
class QuotaResult:
    namespace: Namespace
    cpu_pct: float | None  # None when the limit is unset
    memory_pct: float | None
    issues: list  # e.g. ["cpu at 95.0%"]


def _pct(used: float, limit: float) -> float | None:
    if limit <= 0:
        return None
    return used / limit * 100


def check_quotas(namespaces: list, threshold_pct: float = 90.0) -> list:
    results = []
    for namespace in namespaces:
        issues = []
        cpu = _pct(namespace.cpu_used, namespace.cpu_limit)
        memory = _pct(namespace.memory_used, namespace.memory_limit)
        if cpu is not None and cpu >= threshold_pct:
            issues.append(f"cpu at {cpu:.1f}%")
        if memory is not None and memory >= threshold_pct:
            issues.append(f"memory at {memory:.1f}%")
        results.append(QuotaResult(namespace, cpu, memory, issues))
    return results


def to_markdown(results: list) -> str:
    with_issues = [r for r in results if r.issues]
    lines = ["# Namespace resource quotas", ""]
    lines.append(f"- Namespaces checked: {len(results)}")
    lines.append(f"- Namespaces over threshold: {len(with_issues)}")
    lines.append("")
    if not results:
        lines.append("No namespaces to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Quotas")
    lines.append("| Namespace | CPU % | Memory % | Issues |")
    lines.append("| --------- | ----- | -------- | ------ |")
    for result in sorted(results, key=lambda r: r.namespace.name):
        cpu = f"{result.cpu_pct:.1f}" if result.cpu_pct is not None else "n/a"
        memory = (
            f"{result.memory_pct:.1f}" if result.memory_pct is not None else "n/a"
        )
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {result.namespace.name} | {cpu} | {memory} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def namespaces_from_json(data: list) -> list:
    return [
        Namespace(
            name=item.get("name", "unnamed"),
            cpu_limit=float(item.get("cpu_limit", 0.0)),
            cpu_used=float(item.get("cpu_used", 0.0)),
            memory_limit=float(item.get("memory_limit", 0.0)),
            memory_used=float(item.get("memory_used", 0.0)),
        )
        for item in data
    ]
