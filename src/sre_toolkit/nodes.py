"""Cluster node health.

A node that isn't ready and a node running at 110% of its capacity
are the same incident at different speeds. This checks a JSON list of
cluster nodes for not-ready status and CPU/memory over-commitment, so
the sick nodes get drained before the scheduler keeps piling work
onto them.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Node:
    name: str
    status: str = "ready"  # ready, notready
    cpu_capacity: float = 0.0
    cpu_requested: float = 0.0
    memory_capacity: float = 0.0  # GiB
    memory_requested: float = 0.0  # GiB


@dataclass
class NodeResult:
    node: Node
    cpu_pct: float | None  # None when capacity is unknown
    memory_pct: float | None
    issues: list  # e.g. ["not ready", "cpu over-committed"]


def _pct(requested: float, capacity: float) -> float | None:
    if capacity <= 0:
        return None
    return requested / capacity * 100


def check_nodes(nodes: list, overcommit_pct: float = 100.0) -> list:
    results = []
    for node in nodes:
        issues = []
        cpu = _pct(node.cpu_requested, node.cpu_capacity)
        memory = _pct(node.memory_requested, node.memory_capacity)
        if node.status.lower() != "ready":
            issues.append("not ready")
        if cpu is not None and cpu > overcommit_pct:
            issues.append("cpu over-committed")
        if memory is not None and memory > overcommit_pct:
            issues.append("memory over-committed")
        results.append(NodeResult(node, cpu, memory, issues))
    return results


def to_markdown(results: list) -> str:
    with_issues = [r for r in results if r.issues]
    lines = ["# Cluster node health", ""]
    lines.append(f"- Nodes checked: {len(results)}")
    lines.append(f"- Nodes with issues: {len(with_issues)}")
    lines.append("")
    if not results:
        lines.append("No nodes to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Nodes")
    lines.append("| Node | Status | CPU % | Memory % | Issues |")
    lines.append("| ---- | ------ | ----- | -------- | ------ |")
    for result in sorted(results, key=lambda r: r.node.name):
        cpu = f"{result.cpu_pct:.1f}" if result.cpu_pct is not None else "n/a"
        memory = (
            f"{result.memory_pct:.1f}" if result.memory_pct is not None else "n/a"
        )
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {result.node.name} | {result.node.status} | {cpu} "
            f"| {memory} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def nodes_from_json(data: list) -> list:
    return [
        Node(
            name=item.get("name", "unnamed"),
            status=item.get("status", "ready"),
            cpu_capacity=float(item.get("cpu_capacity", 0.0)),
            cpu_requested=float(item.get("cpu_requested", 0.0)),
            memory_capacity=float(item.get("memory_capacity", 0.0)),
            memory_requested=float(item.get("memory_requested", 0.0)),
        )
        for item in data
    ]
