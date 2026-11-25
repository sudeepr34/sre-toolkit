"""LimitRange audit.

A LimitRange with no default CPU or memory lets every pod
in the namespace run unbounded, so one hungry workload can
starve its neighbours — and a LimitRange with no max lets
a single pod request the whole node. This checks a JSON list
of LimitRanges and flags the ones missing defaults or maxes,
or with no owner, so the guardrails are set before the next
noisy neighbour takes the namespace down with it.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LimitRange:
    name: str = "unnamed"
    namespace: str = "default"
    has_default_cpu: bool = False
    has_default_memory: bool = False
    has_max_cpu: bool = False
    has_max_memory: bool = False
    owner: str = ""


@dataclass
class LimitRangeResult:
    limit_range: LimitRange
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["no default cpu"]


def check_limit_ranges(limit_ranges: list) -> list:
    results = []
    for item in limit_ranges:
        issues = []
        blocked = False
        if not item.has_default_cpu:
            issues.append("no default cpu")
            blocked = True
        if not item.has_default_memory:
            issues.append("no default memory")
            blocked = True
        if not item.has_max_cpu:
            issues.append("no max cpu")
        if not item.has_max_memory:
            issues.append("no max memory")
        if not item.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(LimitRangeResult(item, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# LimitRange audit", ""]
    lines.append(f"- LimitRanges checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No LimitRanges to check.")
        return "\n".join(lines) + "\n"
    lines.append("## LimitRanges")
    lines.append(
        "| LimitRange | Namespace | Default CPU | Default memory "
        "| Max CPU | Max memory | Owner | Verdict | Issues |"
    )
    lines.append(
        "| ---------- | --------- | ----------- | -------------- "
        "| ------- | ---------- | ----- | ------- | ------ |"
    )
    for result in sorted(
        results, key=lambda r: (r.limit_range.namespace, r.limit_range.name)
    ):
        item = result.limit_range
        default_cpu = "yes" if item.has_default_cpu else "no"
        default_mem = "yes" if item.has_default_memory else "no"
        max_cpu = "yes" if item.has_max_cpu else "no"
        max_mem = "yes" if item.has_max_memory else "no"
        owner = item.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {item.name} | {item.namespace} | {default_cpu} | "
            f"{default_mem} | {max_cpu} | {max_mem} | {owner} | "
            f"{result.verdict} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def limit_ranges_from_json(data: list) -> list:
    return [
        LimitRange(
            name=item.get("name", "unnamed"),
            namespace=item.get("namespace", "default"),
            has_default_cpu=bool(item.get("has_default_cpu", False)),
            has_default_memory=bool(item.get("has_default_memory", False)),
            has_max_cpu=bool(item.get("has_max_cpu", False)),
            has_max_memory=bool(item.get("has_max_memory", False)),
            owner=item.get("owner", ""),
        )
        for item in data
    ]
