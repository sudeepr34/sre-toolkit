"""Deployment rollout progress analysis.

A rollout that stops moving is a deploy that needs a human. This reads
deployment snapshots and flags rollouts that are stuck past their
deadline or have failed, so a pipeline can gate on the result. Exit
code 1 when anything is stuck or failed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


def _parse_ts(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


@dataclass
class Rollout:
    name: str
    service: str
    status: str = "progressing"  # progressing, complete, failed
    started: str = ""  # ISO timestamp
    deadline_minutes: float = 30.0
    progress_pct: float = 0.0


@dataclass
class RolloutResult:
    rollout: Rollout
    status: str  # ok, stuck, failed
    detail: str

    @property
    def name(self) -> str:
        return self.rollout.name


def check_rollouts(rollouts: list, now: datetime | None = None) -> list:
    moment = now or datetime.now()
    results = []
    for rollout in rollouts:
        if rollout.status == "complete":
            results.append(
                RolloutResult(rollout, "ok", f"complete ({rollout.progress_pct:g}% done)")
            )
        elif rollout.status == "failed":
            results.append(RolloutResult(rollout, "failed", "rollout failed"))
        elif rollout.status == "progressing":
            started = _parse_ts(rollout.started)
            if started is None:
                results.append(
                    RolloutResult(rollout, "stuck", "started time unreadable")
                )
                continue
            elapsed = (moment - started).total_seconds() / 60
            if elapsed > rollout.deadline_minutes:
                results.append(
                    RolloutResult(
                        rollout, "stuck",
                        f"progressing for {elapsed:.0f}m past "
                        f"{rollout.deadline_minutes:g}m deadline "
                        f"at {rollout.progress_pct:g}%",
                    )
                )
            else:
                results.append(
                    RolloutResult(
                        rollout, "ok",
                        f"progressing {elapsed:.0f}m in, "
                        f"{rollout.progress_pct:g}% done",
                    )
                )
        else:
            results.append(
                RolloutResult(rollout, "stuck", f"unknown status {rollout.status!r}")
            )
    return results


def to_markdown(results: list) -> str:
    lines = ["# Rollout status", ""]
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    summary = ", ".join(f"{n} {status}" for status, n in sorted(counts.items()))
    lines.append(f"- Checked {len(results)} rollouts: {summary}")
    lines.append("")
    lines.append("| Rollout | Service | Status | Detail |")
    lines.append("| ------- | ------- | ------ | ------ |")
    for result in results:
        lines.append(
            f"| {result.name} | {result.rollout.service} | {result.status} | {result.detail} |"
        )
    lines.append("")
    problems = [r for r in results if r.status != "ok"]
    if problems:
        lines.append("## Needs attention")
        for result in problems:
            lines.append(f"- {result.name}: {result.detail}")
    else:
        lines.append("All rollouts healthy.")
    return "\n".join(lines) + "\n"


def rollouts_from_json(data: list) -> list:
    return [
        Rollout(
            name=item.get("name", "unnamed"),
            service=item.get("service", "unnamed"),
            status=item.get("status", "progressing"),
            started=item.get("started", ""),
            deadline_minutes=float(item.get("deadline_minutes", 30)),
            progress_pct=float(item.get("progress_pct", 0)),
        )
        for item in data
    ]
