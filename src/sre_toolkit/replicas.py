"""Replica count audit.

A deployment with fewer ready replicas than desired is degraded, and
one with zero ready is down. This checks a JSON list of deployments
and reports the under-replicated ones, so the gap is caught by the
checker instead of by the first failed request.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Deployment:
    name: str
    namespace: str = "default"
    desired: int = 1
    ready: int = 0


@dataclass
class ReplicaResult:
    deployment: Deployment
    ready_pct: float | None  # None when desired is zero
    status: str  # ok, degraded, down


def check_replicas(deployments: list) -> list:
    results = []
    for deployment in deployments:
        if deployment.ready <= 0:
            status = "down"
        elif deployment.ready < deployment.desired:
            status = "degraded"
        else:
            status = "ok"
        ready_pct = (
            deployment.ready / deployment.desired * 100
            if deployment.desired > 0
            else None
        )
        results.append(ReplicaResult(deployment, ready_pct, status))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    lines = ["# Replica count audit", ""]
    lines.append(f"- Deployments checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Degraded: {counts.get('degraded', 0)}")
    lines.append(f"- Down: {counts.get('down', 0)}")
    lines.append("")
    if not results:
        lines.append("No deployments to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Deployments")
    lines.append("| Deployment | Namespace | Desired | Ready | Ready % | Status |")
    lines.append("| ---------- | --------- | ------- | ----- | ------- | ------ |")
    for result in sorted(results, key=lambda r: r.deployment.name):
        pct = (
            f"{result.ready_pct:.1f}" if result.ready_pct is not None else "n/a"
        )
        lines.append(
            f"| {result.deployment.name} | {result.deployment.namespace} "
            f"| {result.deployment.desired} | {result.deployment.ready} "
            f"| {pct} | {result.status} |"
        )
    return "\n".join(lines) + "\n"


def deployments_from_json(data: list) -> list:
    return [
        Deployment(
            name=item.get("name", "unnamed"),
            namespace=item.get("namespace", "default"),
            desired=int(item.get("desired", 1)),
            ready=int(item.get("ready", 0)),
        )
        for item in data
    ]
