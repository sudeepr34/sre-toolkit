"""Persistent volume usage.

A volume that fills up takes the pod writing to it down with it, and
the failure looks like an application bug until someone checks the
disk. This checks a JSON list of persistent volumes and flags the ones
over the usage threshold, so the volume is expanded — or the data
cleaned up — before writes start failing.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Volume:
    name: str
    namespace: str = "default"
    capacity_gi: float = 0.0
    used_gi: float = 0.0


@dataclass
class VolumeResult:
    volume: Volume
    used_pct: float | None  # None when capacity is unknown
    status: str  # ok, warning, critical


def check_volumes(volumes: list, warning_pct: float = 80.0, critical_pct: float = 95.0) -> list:
    results = []
    for volume in volumes:
        used_pct = (
            volume.used_gi / volume.capacity_gi * 100
            if volume.capacity_gi > 0
            else None
        )
        if used_pct is None:
            status = "ok"
        elif used_pct >= critical_pct:
            status = "critical"
        elif used_pct >= warning_pct:
            status = "warning"
        else:
            status = "ok"
        results.append(VolumeResult(volume, used_pct, status))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    lines = ["# Persistent volume usage", ""]
    lines.append(f"- Volumes checked: {len(results)}")
    lines.append(f"- Critical: {counts.get('critical', 0)}")
    lines.append(f"- Warning: {counts.get('warning', 0)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append("")
    if not results:
        lines.append("No volumes to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Volumes")
    lines.append("| Volume | Namespace | Capacity Gi | Used Gi | Used % | Status |")
    lines.append("| ------ | --------- | ----------- | ------- | ------ | ------ |")
    for result in sorted(
        results, key=lambda r: (r.used_pct or 0), reverse=True
    ):
        pct = f"{result.used_pct:.1f}" if result.used_pct is not None else "n/a"
        lines.append(
            f"| {result.volume.name} | {result.volume.namespace} "
            f"| {result.volume.capacity_gi:g} | {result.volume.used_gi:g} "
            f"| {pct} | {result.status} |"
        )
    return "\n".join(lines) + "\n"


def volumes_from_json(data: list) -> list:
    return [
        Volume(
            name=item.get("name", "unnamed"),
            namespace=item.get("namespace", "default"),
            capacity_gi=float(item.get("capacity_gi", 0.0)),
            used_gi=float(item.get("used_gi", 0.0)),
        )
        for item in data
    ]
