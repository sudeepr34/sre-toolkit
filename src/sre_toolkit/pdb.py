"""PodDisruptionBudget audit.

A PodDisruptionBudget that allows zero disruptions turns every
node drain into a stuck rollout: the drain waits forever and the
node never leaves. This checks a JSON list of PDBs and flags the
ones that block drains, constrain nothing, or have no owner, so
the budget is loosened — or removed — before the next node
upgrade stalls.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PodDisruptionBudget:
    name: str = "unnamed"
    namespace: str = "default"
    min_available: int | None = None
    max_unavailable: int | None = None
    disruptions_allowed: int = 0
    replicas: int = 0
    owner: str = ""


@dataclass
class PdbResult:
    pdb: PodDisruptionBudget
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["blocks all drains"]


def check_pdbs(pdbs: list) -> list:
    results = []
    for pdb in pdbs:
        issues = []
        blocked = False
        if pdb.min_available is None and pdb.max_unavailable is None:
            issues.append("no min or max set")
            blocked = True
        if (
            pdb.min_available is not None
            and pdb.replicas > 0
            and pdb.min_available >= pdb.replicas
        ):
            issues.append("min available equals replicas")
            blocked = True
        if pdb.disruptions_allowed == 0:
            issues.append("blocks all drains")
            blocked = True
        if pdb.max_unavailable == 0:
            issues.append("max unavailable is 0")
            blocked = True
        if not pdb.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(PdbResult(pdb, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# PodDisruptionBudget audit", ""]
    lines.append(f"- PDBs checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No PDBs to check.")
        return "\n".join(lines) + "\n"
    lines.append("## PDBs")
    lines.append(
        "| Namespace | PDB | Min available | Max unavailable "
        "| Disruptions allowed | Replicas | Owner | Verdict | Issues |"
    )
    lines.append(
        "| --------- | --- | ------------- | --------------- "
        "| ------------------- | -------- | ----- | ------- | ------ |"
    )
    for result in sorted(
        results, key=lambda r: (r.pdb.namespace, r.pdb.name)
    ):
        pdb = result.pdb
        minimum = str(pdb.min_available) if pdb.min_available is not None else "—"
        maximum = (
            str(pdb.max_unavailable)
            if pdb.max_unavailable is not None
            else "—"
        )
        owner = pdb.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {pdb.namespace} | {pdb.name} | {minimum} | {maximum} "
            f"| {pdb.disruptions_allowed} | {pdb.replicas} | {owner} "
            f"| {result.verdict} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def pdbs_from_json(data: list) -> list:
    pdbs = []
    for item in data:
        minimum = item.get("min_available")
        maximum = item.get("max_unavailable")
        pdbs.append(
            PodDisruptionBudget(
                name=item.get("name", "unnamed"),
                namespace=item.get("namespace", "default"),
                min_available=None if minimum is None else int(minimum),
                max_unavailable=None if maximum is None else int(maximum),
                disruptions_allowed=int(item.get("disruptions_allowed", 0)),
                replicas=int(item.get("replicas", 0)),
                owner=item.get("owner", ""),
            )
        )
    return pdbs
