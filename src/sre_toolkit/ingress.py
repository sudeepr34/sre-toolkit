"""Ingress route audit.

An Ingress without TLS serves traffic in the clear, one with no
backend service routes nowhere, and two claiming the same host fight
over routing. This checks a JSON list of ingresses and flags the
ones that expose, misroute, or conflict, so the route is fixed —
or the duplicate removed — before traffic lands on the wrong
service.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Ingress:
    name: str = "unnamed"
    namespace: str = "default"
    host: str = ""
    service: str = ""
    tls: bool = False
    owner: str = ""


@dataclass
class IngressResult:
    ingress: Ingress
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["no TLS"]


def check_ingresses(ingresses: list) -> list:
    hosts: dict[str, int] = {}
    for ingress in ingresses:
        if ingress.host:
            hosts[ingress.host] = hosts.get(ingress.host, 0) + 1
    results = []
    for ingress in ingresses:
        issues = []
        blocked = False
        if not ingress.tls:
            issues.append("no TLS")
            blocked = True
        if not ingress.service:
            issues.append("no backend service")
            blocked = True
        if not ingress.host:
            issues.append("no host")
            blocked = True
        if ingress.host and hosts[ingress.host] > 1:
            issues.append("duplicate host")
        if not ingress.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(IngressResult(ingress, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# Ingress route audit", ""]
    lines.append(f"- Ingresses checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No ingresses to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Ingresses")
    lines.append("| Namespace | Ingress | Host | Service | TLS | Owner | Verdict | Issues |")
    lines.append("| --------- | ------- | ---- | ------- | --- | ----- | ------- | ------ |")
    for result in sorted(
        results, key=lambda r: (r.ingress.namespace, r.ingress.name)
    ):
        ingress = result.ingress
        tls = "yes" if ingress.tls else "no"
        host = ingress.host or "—"
        service = ingress.service or "—"
        owner = ingress.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {ingress.namespace} | {ingress.name} | {host} | {service} "
            f"| {tls} | {owner} | {result.verdict} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def ingresses_from_json(data: list) -> list:
    return [
        Ingress(
            name=item.get("name", "unnamed"),
            namespace=item.get("namespace", "default"),
            host=item.get("host", ""),
            service=item.get("service", ""),
            tls=bool(item.get("tls", False)),
            owner=item.get("owner", ""),
        )
        for item in data
    ]
