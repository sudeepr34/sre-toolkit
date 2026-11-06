"""Latency percentile analysis.

Averages hide tail latency; percentiles don't. This computes p50/p95/p99
from a list of latency samples (milliseconds) and gates the p95 against
an SLO threshold, so a slow tail fails the gate instead of hiding behind
a healthy mean.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class LatencyStats:
    count: int
    minimum: float
    maximum: float
    mean: float
    p50: float
    p95: float
    p99: float


def percentile(sorted_samples: list, pct: float) -> float:
    """Nearest-rank percentile: the value at ceil(p/100 * n), 1-based."""
    if not sorted_samples:
        raise ValueError("no samples")
    rank = math.ceil(pct / 100 * len(sorted_samples)) - 1
    return sorted_samples[max(0, min(rank, len(sorted_samples) - 1))]


def analyze(samples: list) -> LatencyStats:
    ordered = sorted(samples)
    if not ordered:
        raise ValueError("no samples")
    return LatencyStats(
        count=len(ordered),
        minimum=ordered[0],
        maximum=ordered[-1],
        mean=sum(ordered) / len(ordered),
        p50=percentile(ordered, 50),
        p95=percentile(ordered, 95),
        p99=percentile(ordered, 99),
    )


def breached(stats: LatencyStats, p95_threshold_ms: float) -> bool:
    """True when the p95 exceeds the threshold; exactly at it passes."""
    return stats.p95 > p95_threshold_ms


def to_markdown(stats: LatencyStats, p95_threshold_ms: float) -> str:
    lines = ["# Latency percentiles", ""]
    lines.append(f"- Samples: {stats.count}")
    lines.append(f"- Min: {stats.minimum:.1f} ms")
    lines.append(f"- Mean: {stats.mean:.1f} ms")
    lines.append(f"- Max: {stats.maximum:.1f} ms")
    lines.append("")
    lines.append("| Percentile | Latency (ms) |")
    lines.append("| ---------- | ------------ |")
    lines.append(f"| p50 | {stats.p50:.1f} |")
    lines.append(f"| p95 | {stats.p95:.1f} |")
    lines.append(f"| p99 | {stats.p99:.1f} |")
    lines.append("")
    lines.append(
        f"- p95 threshold: {p95_threshold_ms:.1f} ms — "
        + ("BREACH" if breached(stats, p95_threshold_ms) else "within threshold")
    )
    return "\n".join(lines) + "\n"
