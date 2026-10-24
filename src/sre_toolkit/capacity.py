"""Capacity planning.

Projects load growth against current capacity and answers the two
questions that matter in a planning review: when does utilization cross
the target ceiling, and how much capacity would bring it back under?
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CapacityPlan:
    current_load: float
    capacity: float
    growth_rate: float  # per period, e.g. 0.05 = 5% growth per period
    target_utilization: float = 0.70
    periods: int = 12
    unit: str = "rps"

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise ValueError("capacity must be positive")
        if self.current_load < 0:
            raise ValueError("current_load cannot be negative")
        if not 0 < self.target_utilization <= 1:
            raise ValueError("target_utilization must be in (0, 1]")
        if self.periods < 0:
            raise ValueError("periods cannot be negative")

    def projected_load(self, period: int) -> float:
        """Load at the end of the given period under compound growth."""
        if period < 0:
            raise ValueError("period cannot be negative")
        return self.current_load * (1 + self.growth_rate) ** period

    def utilization(self, period: int) -> float:
        """Fraction of capacity used at the end of the given period."""
        return self.projected_load(period) / self.capacity

    def forecast(self) -> list:
        """One (period, load, utilization) tuple per period, 0..periods."""
        return [
            (p, self.projected_load(p), self.utilization(p))
            for p in range(self.periods + 1)
        ]

    def breach_period(self) -> int | None:
        """First period where utilization exceeds the target, else None."""
        for period, _load, util in self.forecast():
            if util > self.target_utilization:
                return period
        return None

    def capacity_needed(self, period: int) -> float:
        """Capacity that would hold the period's load at target utilization."""
        return self.projected_load(period) / self.target_utilization

    def to_markdown(self) -> str:
        lines = ["# Capacity forecast", ""]
        lines.append(
            f"- Current load: {self.current_load:g} {self.unit} "
            f"on {self.capacity:g} {self.unit} capacity"
        )
        lines.append(
            f"- Growth: {self.growth_rate * 100:g}% per period "
            f"| Target utilization: {self.target_utilization * 100:g}%"
        )
        lines.append("")
        lines.append("| Period | Projected load | Utilization | Status |")
        lines.append("| ------ | -------------- | ----------- | ------ |")
        for period, load, util in self.forecast():
            status = "breach" if util > self.target_utilization else "ok"
            lines.append(
                f"| {period} | {load:,.1f} {self.unit} | {util * 100:.1f}% | {status} |"
            )
        lines.append("")
        breach = self.breach_period()
        if breach is None:
            lines.append(
                f"Utilization stays under target for all {self.periods} periods."
            )
        else:
            needed = self.capacity_needed(breach)
            lines.append(
                f"Utilization crosses target at period {breach}. "
                f"Scale capacity to at least {needed:,.1f} {self.unit} "
                f"({needed / self.capacity:.2f}x current) before then."
            )
        return "\n".join(lines) + "\n"
