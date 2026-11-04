"""Queue backlog analysis.

A growing queue is usually the first sign a consumer is falling behind
or a downstream dependency is sick. This checks each queue's depth and
oldest-item age against its thresholds and flags breaches — depth,
age, or both — so the team sees the backlog before it becomes an
incident. Exit code 1 when any queue breaches, for CI gating.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QueueSnapshot:
    queue: str
    depth: int = 0
    oldest_age_minutes: float = 0.0
    max_depth: int = 1000
    max_age_minutes: float = 60.0


@dataclass
class QueueResult:
    snapshot: QueueSnapshot
    status: str  # ok, breach
    detail: str

    @property
    def queue(self) -> str:
        return self.snapshot.queue


def check_queues(snapshots: list) -> list:
    results = []
    for snap in snapshots:
        breaches = []
        if snap.depth > snap.max_depth:
            breaches.append(
                f"depth {snap.depth} over max {snap.max_depth}"
            )
        if snap.oldest_age_minutes > snap.max_age_minutes:
            breaches.append(
                f"oldest item {snap.oldest_age_minutes:g}m over max "
                f"{snap.max_age_minutes:g}m"
            )
        if breaches:
            results.append(QueueResult(snap, "breach", "; ".join(breaches)))
        else:
            results.append(
                QueueResult(
                    snap, "ok",
                    f"depth {snap.depth} (max {snap.max_depth}), "
                    f"oldest {snap.oldest_age_minutes:g}m "
                    f"(max {snap.max_age_minutes:g}m)",
                )
            )
    return results


def to_markdown(results: list) -> str:
    lines = ["# Queue backlog", ""]
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    summary = ", ".join(f"{n} {status}" for status, n in sorted(counts.items()))
    lines.append(f"- Checked {len(results)} queues: {summary}")
    lines.append("")
    lines.append("| Queue | Status | Detail |")
    lines.append("| ----- | ------ | ------ |")
    for result in results:
        lines.append(f"| {result.queue} | {result.status} | {result.detail} |")
    lines.append("")
    breaches = [r for r in results if r.status == "breach"]
    if breaches:
        lines.append("## Breaches")
        for result in breaches:
            lines.append(f"- {result.queue}: {result.detail}")
    else:
        lines.append("All queues within thresholds.")
    return "\n".join(lines) + "\n"


def snapshots_from_json(data: list) -> list:
    return [
        QueueSnapshot(
            queue=item.get("queue", "unnamed"),
            depth=int(item.get("depth", 0)),
            oldest_age_minutes=float(item.get("oldest_age_minutes", 0)),
            max_depth=int(item.get("max_depth", 1000)),
            max_age_minutes=float(item.get("max_age_minutes", 60)),
        )
        for item in data
    ]
