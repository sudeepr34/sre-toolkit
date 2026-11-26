"""Service endpoints audit.

A Service with no ready endpoints black-holes traffic: kube-proxy
still programs the ClusterIP, but every request has nowhere to go.
A Service down to a single ready endpoint is one pod crash away
from the same, and a Service whose ready count trails its total is
already degraded. This checks a JSON list of Services and flags
the ones with no ready endpoints, partial readiness, a single
ready endpoint, or no owner, so the routing is fixed before the
next zone failure or rollout drains the last backend.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Endpoints:
    name: str = "unnamed"
    namespace: str = "default"
    ready_endpoints: int = 0
    total_endpoints: int = 0
    owner: str = ""


@dataclass
class EndpointsResult:
    service: Endpoints
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["no ready endpoints"]


def check_endpoints(services: list) -> list:
    results = []
    for item in services:
        issues = []
        blocked = False
        if item.ready_endpoints <= 0:
            issues.append("no ready endpoints")
            blocked = True
        elif item.ready_endpoints == 1:
            issues.append("single ready endpoint")
        if item.total_endpoints > item.ready_endpoints > 0:
            issues.append("partial readiness")
        if not item.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(EndpointsResult(item, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# Service endpoints audit", ""]
    lines.append(f"- Services checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No services to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Services")
    lines.append(
        "| Service | Namespace | Ready | Total | Owner | Verdict | Issues |"
    )
    lines.append(
        "| ------- | --------- | ----- | ----- | ----- | ------- | ------ |"
    )
    for result in sorted(
        results, key=lambda r: (r.service.namespace, r.service.name)
    ):
        item = result.service
        owner = item.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {item.name} | {item.namespace} | {item.ready_endpoints} | "
            f"{item.total_endpoints} | {owner} | {result.verdict} | "
            f"{issues} |"
        )
    return "\n".join(lines) + "\n"


def endpoints_from_json(data: list) -> list:
    return [
        Endpoints(
            name=item.get("name", "unnamed"),
            namespace=item.get("namespace", "default"),
            ready_endpoints=int(item.get("ready_endpoints", 0)),
            total_endpoints=int(item.get("total_endpoints", 0)),
            owner=item.get("owner", ""),
        )
        for item in data
    ]
