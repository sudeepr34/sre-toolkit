"""Canary analysis.

Compares a canary deployment against its baseline on error rate and
p99 latency and gives a verdict: promote, hold (not enough data yet),
or rollback. Exit 0 only on promote; anything else blocks the rollout.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CanaryAnalysis:
    canary_error_rate: float  # fraction, e.g. 0.02 = 2% errors
    baseline_error_rate: float
    canary_p99_ms: float
    baseline_p99_ms: float
    canary_requests: int
    max_error_delta: float = 0.01  # allowed error-rate rise, in points
    max_p99_ratio: float = 1.5  # allowed canary p99 / baseline p99
    min_requests: int = 100

    def error_delta(self) -> float:
        return self.canary_error_rate - self.baseline_error_rate

    def p99_ratio(self) -> float | None:
        if self.baseline_p99_ms <= 0:
            return None
        return self.canary_p99_ms / self.baseline_p99_ms

    def verdict(self) -> str:
        """promote, hold, or rollback."""
        if self.canary_requests < self.min_requests:
            return "hold"
        if self.error_delta() > self.max_error_delta:
            return "rollback"
        ratio = self.p99_ratio()
        if ratio is not None and ratio > self.max_p99_ratio:
            return "rollback"
        return "promote"

    def reasons(self) -> list:
        notes = []
        if self.canary_requests < self.min_requests:
            notes.append(
                f"only {self.canary_requests} requests, need {self.min_requests}"
            )
        if self.error_delta() > self.max_error_delta:
            notes.append(
                f"error rate up {self.error_delta() * 100:.2f} points "
                f"(max {self.max_error_delta * 100:.2f})"
            )
        ratio = self.p99_ratio()
        if ratio is not None and ratio > self.max_p99_ratio:
            notes.append(
                f"p99 {ratio:.2f}x baseline (max {self.max_p99_ratio:.2f}x)"
            )
        if not notes:
            notes.append("within thresholds")
        return notes

    def to_markdown(self) -> str:
        lines = ["# Canary analysis", ""]
        lines.append(f"- Canary requests: {self.canary_requests}")
        lines.append(
            f"- Error rate: canary {self.canary_error_rate * 100:.2f}% "
            f"vs baseline {self.baseline_error_rate * 100:.2f}% "
            f"(delta {self.error_delta() * 100:+.2f} points)"
        )
        ratio = self.p99_ratio()
        ratio_text = f"{ratio:.2f}x" if ratio is not None else "n/a"
        lines.append(
            f"- p99 latency: canary {self.canary_p99_ms:g}ms "
            f"vs baseline {self.baseline_p99_ms:g}ms ({ratio_text})"
        )
        lines.append("")
        lines.append(f"## Verdict: {self.verdict().upper()}")
        for note in self.reasons():
            lines.append(f"- {note}")
        return "\n".join(lines) + "\n"
