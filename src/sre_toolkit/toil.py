"""Toil tracking.

Google SRE's rule is that toil — manual, repetitive, automatable work
with no enduring value — should stay under 50% of an SRE team's time.
This turns a JSON list of toil entries into a report: where the time
goes, what share of capacity it eats, and which tasks are the best
automation candidates.
"""
from __future__ import annotations

from dataclasses import dataclass

TOIL_BUDGET_PCT = 50.0
AUTOMATABLE_CATEGORIES = ("manual", "automatable")


@dataclass
class ToilEntry:
    task: str
    minutes: float
    category: str = "manual"  # manual, automatable, operational
    date: str = ""  # YYYY-MM-DD


def total_minutes(entries: list) -> float:
    return sum(e.minutes for e in entries)


def by_task(entries: list) -> list:
    """(task, minutes) pairs, most time first."""
    totals: dict[str, float] = {}
    for entry in entries:
        totals[entry.task] = totals.get(entry.task, 0.0) + entry.minutes
    return sorted(totals.items(), key=lambda item: item[1], reverse=True)


def by_category(entries: list) -> list:
    """(category, minutes) pairs, most time first."""
    totals: dict[str, float] = {}
    for entry in entries:
        totals[entry.category] = totals.get(entry.category, 0.0) + entry.minutes
    return sorted(totals.items(), key=lambda item: item[1], reverse=True)


def toil_percentage(entries: list, capacity_minutes: float) -> float | None:
    """Toil as a share of available capacity; None when capacity is 0."""
    if capacity_minutes <= 0:
        return None
    return total_minutes(entries) / capacity_minutes * 100


def automation_candidates(entries: list, min_minutes: float = 120.0) -> list:
    """Automatable tasks worth scripting, most time first.

    Groups minutes per task, keeps only tasks whose entries are in an
    automatable category, and filters to tasks at or above the threshold.
    """
    totals: dict[str, float] = {}
    for entry in entries:
        if entry.category in AUTOMATABLE_CATEGORIES:
            totals[entry.task] = totals.get(entry.task, 0.0) + entry.minutes
    return sorted(
        ((task, minutes) for task, minutes in totals.items()
         if minutes >= min_minutes),
        key=lambda item: item[1],
        reverse=True,
    )


def to_markdown(
    entries: list,
    capacity_minutes: float = 0.0,
    min_minutes: float = 120.0,
) -> str:
    lines = ["# Toil report", ""]
    total = total_minutes(entries)
    lines.append(f"- Total toil: {total:,.0f} minutes ({total / 60:.1f} hours)")
    if capacity_minutes > 0:
        pct = toil_percentage(entries, capacity_minutes)
        lines.append(
            f"- Share of capacity: {pct:.1f}% "
            f"(budget: under {TOIL_BUDGET_PCT:.0f}%)"
        )
        if pct is not None and pct > TOIL_BUDGET_PCT:
            lines.append(f"- ⚠ Toil is over budget by {pct - TOIL_BUDGET_PCT:.1f} points")
    lines.append("")
    lines.append("## By task")
    lines.append("| Task | Minutes | Share |")
    lines.append("| ---- | ------- | ----- |")
    for task, minutes in by_task(entries):
        share = (minutes / total * 100) if total else 0.0
        lines.append(f"| {task} | {minutes:,.0f} | {share:.1f}% |")
    lines.append("")
    lines.append("## By category")
    for category, minutes in by_category(entries):
        lines.append(f"- {category}: {minutes:,.0f} minutes")
    lines.append("")
    candidates = automation_candidates(entries, min_minutes)
    if candidates:
        lines.append("## Automation candidates")
        for task, minutes in candidates:
            lines.append(f"- {task}: {minutes:,.0f} minutes")
    else:
        lines.append("No automation candidates above the threshold.")
    return "\n".join(lines) + "\n"


def entries_from_json(data: list) -> list:
    return [
        ToilEntry(
            task=item.get("task", "unnamed"),
            minutes=float(item.get("minutes", 0)),
            category=item.get("category", "manual"),
            date=item.get("date", ""),
        )
        for item in data
    ]
