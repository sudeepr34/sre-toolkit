"""Service health rollup.

Takes a JSON list of per-service health checks and answers the one
question a status meeting needs: how bad is it right now? Overall
status is the worst of any service (down beats degraded beats up),
with the degraded and down services named.
"""
from __future__ import annotations

from dataclasses import dataclass

STATUS_RANK = {"up": 0, "degraded": 1, "down": 2}


@dataclass
class HealthCheck:
    service: str
    status: str = "up"  # up, degraded, down
    latency_ms: float | None = None


def overall_status(checks: list) -> str:
    """Worst status across all checks; 'up' when there are none."""
    worst = "up"
    for check in checks:
        rank = STATUS_RANK.get(check.status.lower(), 0)
        if rank > STATUS_RANK[worst]:
            worst = check.status.lower()
    return worst


def slowest(checks: list) -> HealthCheck | None:
    """The check with the highest latency, if any latency is recorded."""
    measured = [c for c in checks if c.latency_ms is not None]
    if not measured:
        return None
    return max(measured, key=lambda c: c.latency_ms)


def to_markdown(checks: list) -> str:
    lines = ["# Service health", ""]
    lines.append(f"- Overall: **{overall_status(checks)}**")
    counts: dict[str, int] = {}
    for check in checks:
        counts[check.status.lower()] = counts.get(check.status.lower(), 0) + 1
    summary = ", ".join(f"{n} {status}" for status, n in sorted(counts.items()))
    lines.append(f"- Checked {len(checks)} services: {summary}")
    slow = slowest(checks)
    if slow is not None:
        lines.append(f"- Slowest: {slow.service} ({slow.latency_ms:g}ms)")
    lines.append("")
    lines.append("| Service | Status | Latency |")
    lines.append("| ------- | ------ | ------- |")
    for check in checks:
        latency = f"{check.latency_ms:g}ms" if check.latency_ms is not None else "-"
        lines.append(f"| {check.service} | {check.status} | {latency} |")
    lines.append("")
    problems = [c for c in checks if c.status.lower() != "up"]
    if problems:
        lines.append("## Needs attention")
        for check in problems:
            lines.append(f"- {check.service}: {check.status}")
    else:
        lines.append("All services up.")
    return "\n".join(lines) + "\n"


def checks_from_json(data: list) -> list:
    return [
        HealthCheck(
            service=item.get("service", "unnamed"),
            status=item.get("status", "up"),
            latency_ms=(
                float(item["latency_ms"])
                if item.get("latency_ms") is not None else None
            ),
        )
        for item in data
    ]
