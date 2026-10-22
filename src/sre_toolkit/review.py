"""Weekly ops review rollup.

Aggregates a week's postmortems into the summary an SRE team reads at the
weekly ops review: incident counts by severity, mean time-to-mitigate and
time-to-resolve, the most common contributing factors, and every open
follow-up action item. Rendered as Markdown.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .postmortem import Postmortem, format_duration


@dataclass
class WeeklyReview:
    week: str = ""
    postmortems: list = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.postmortems)

    def by_severity(self) -> dict:
        return dict(Counter(pm.severity for pm in self.postmortems))

    def _mean(self, attr: str) -> float | None:
        values = [
            getattr(pm, attr)
            for pm in self.postmortems
            if getattr(pm, attr) is not None
        ]
        if not values:
            return None
        return sum(values) / len(values)

    @property
    def mean_time_to_mitigate(self) -> float | None:
        """Mean TTM in seconds over incidents that recorded it."""
        return self._mean("time_to_mitigate_seconds")

    @property
    def mean_time_to_resolve(self) -> float | None:
        """Mean TTR in seconds over incidents that recorded it."""
        return self._mean("time_to_resolve_seconds")

    def top_factors(self, n: int = 5) -> list:
        """Most common contributing factors as (factor, count) pairs."""
        counts = Counter(
            factor
            for pm in self.postmortems
            for factor in pm.contributing_factors
        )
        return counts.most_common(n)

    def open_action_items(self) -> list:
        """(incident title, action item) pairs for every open follow-up."""
        return [
            (pm.title, item)
            for pm in self.postmortems
            for item in pm.action_items
            if not item.done
        ]

    def to_markdown(self) -> str:
        lines = [f"# Ops review: {self.week or 'week'}", ""]
        lines.append(f"- Incidents reviewed: {self.count}")
        if self.count == 0:
            lines.append("")
            lines.append("_No incidents this week._")
            return "\n".join(lines) + "\n"

        sev = ", ".join(
            f"{name}: {count}"
            for name, count in sorted(self.by_severity().items())
        )
        lines.append(f"- By severity: {sev}")

        ttm = self.mean_time_to_mitigate
        ttr = self.mean_time_to_resolve
        lines.append(
            f"- Mean time to mitigate: {format_duration(ttm) if ttm is not None else 'n/a'}"
        )
        lines.append(
            f"- Mean time to resolve: {format_duration(ttr) if ttr is not None else 'n/a'}"
        )
        lines.append("")

        lines.append("## Top contributing factors")
        factors = self.top_factors()
        if factors:
            for factor, count in factors:
                lines.append(f"- [{count}x] {factor}")
        else:
            lines.append("- _None recorded._")
        lines.append("")

        actions = self.open_action_items()
        lines.append(f"## Open action items ({len(actions)})")
        if actions:
            for title, item in actions:
                due = f", due: {item.due}" if item.due else ""
                lines.append(f"- [ ] {item.task} ({title}; owner: {item.owner}{due})")
        else:
            lines.append("- _None open._")
        return "\n".join(lines) + "\n"


def weekly_review_from_postmortems(
    postmortems: list, week: str = ""
) -> WeeklyReview:
    """Build a WeeklyReview from Postmortem objects."""
    return WeeklyReview(week=week, postmortems=list(postmortems))
