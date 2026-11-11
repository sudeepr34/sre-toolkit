"""Pod restart analysis.

A pod restarting every few minutes is crash-looping, not recovering.
This checks a JSON list of pods and flags the ones whose restart
count crosses a threshold, plus a restart rate per day of age, so the
unstable workloads are named before they take the service down.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Pod:
    name: str
    namespace: str = "default"
    restarts: int = 0
    age_hours: float = 0.0


@dataclass
class PodResult:
    pod: Pod
    restarts_per_day: float | None  # None when age is unknown
    status: str  # ok, warning, critical


def restarts_per_day(pod: Pod) -> float | None:
    if pod.age_hours <= 0:
        return None
    return pod.restarts / pod.age_hours * 24


def check_pods(pods: list, restart_threshold: int = 5) -> list:
    results = []
    for pod in pods:
        rate = restarts_per_day(pod)
        if pod.restarts >= restart_threshold:
            status = "critical"
        elif pod.restarts > 0:
            status = "warning"
        else:
            status = "ok"
        results.append(PodResult(pod, rate, status))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    lines = ["# Pod restart check", ""]
    lines.append(f"- Pods checked: {len(results)}")
    lines.append(f"- Critical: {counts.get('critical', 0)}")
    lines.append(f"- Warning: {counts.get('warning', 0)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append("")
    if not results:
        lines.append("No pods to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Pods")
    lines.append("| Pod | Namespace | Restarts | Restarts/day | Status |")
    lines.append("| --- | --------- | -------- | ------------ | ------ |")
    for result in sorted(
        results, key=lambda r: (r.pod.restarts, r.pod.name), reverse=True
    ):
        rate = (
            f"{result.restarts_per_day:.1f}"
            if result.restarts_per_day is not None
            else "n/a"
        )
        lines.append(
            f"| {result.pod.name} | {result.pod.namespace} "
            f"| {result.pod.restarts} | {rate} | {result.status} |"
        )
    return "\n".join(lines) + "\n"


def pods_from_json(data: list) -> list:
    return [
        Pod(
            name=item.get("name", "unnamed"),
            namespace=item.get("namespace", "default"),
            restarts=int(item.get("restarts", 0)),
            age_hours=float(item.get("age_hours", 0.0)),
        )
        for item in data
    ]
