"""Namespace audit.

A namespace with no ResourceQuota can swallow the whole
cluster's capacity, and one with no NetworkPolicy leaves
every pod in it reachable from anywhere. This checks a JSON
list of namespaces and flags the ones with no quota, no
limits, no network policy, or no owner, so the guardrails
are added before the next noisy neighbour takes the cluster
down with it.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Namespace:
    name: str = "unnamed"
    has_resource_quota: bool = False
    has_limit_range: bool = False
    has_network_policy: bool = False
    owner: str = ""


@dataclass
class NamespaceResult:
    namespace: Namespace
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["no resource quota"]


def check_namespaces(namespaces: list) -> list:
    results = []
    for item in namespaces:
        issues = []
        blocked = False
        if not item.has_resource_quota:
            issues.append("no resource quota")
            blocked = True
        if not item.has_limit_range:
            issues.append("no limit range")
        if not item.has_network_policy:
            issues.append("no network policy")
        if not item.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(NamespaceResult(item, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# Namespace audit", ""]
    lines.append(f"- Namespaces checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No namespaces to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Namespaces")
    lines.append(
        "| Namespace | Resource quota | Limit range "
        "| Network policy | Owner | Verdict | Issues |"
    )
    lines.append(
        "| --------- | -------------- | ----------- "
        "| -------------- | ----- | ------- | ------ |"
    )
    for result in sorted(
        results, key=lambda r: r.namespace.name
    ):
        item = result.namespace
        quota = "yes" if item.has_resource_quota else "no"
        limits = "yes" if item.has_limit_range else "no"
        policy = "yes" if item.has_network_policy else "no"
        owner = item.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {item.name} | {quota} | {limits} | {policy} "
            f"| {owner} | {result.verdict} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def namespaces_from_json(data: list) -> list:
    return [
        Namespace(
            name=item.get("name", "unnamed"),
            has_resource_quota=bool(item.get("has_resource_quota", False)),
            has_limit_range=bool(item.get("has_limit_range", False)),
            has_network_policy=bool(
                item.get("has_network_policy", False)
            ),
            owner=item.get("owner", ""),
        )
        for item in data
    ]
