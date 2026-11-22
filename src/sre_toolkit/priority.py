"""PriorityClass audit.

A PriorityClass with a negative value is rejected by the API
server outright, and two classes both marked as the global
default leave the scheduler guessing which priority an
unmarked pod gets. This checks a JSON list of PriorityClasses
and flags the ones that are invalid, duplicate the default,
or have no owner, so the class is fixed before the next pod
schedules at the wrong priority.
"""
from __future__ import annotations

from dataclasses import dataclass

MAX_VALUE = 1_000_000_000


@dataclass
class PriorityClass:
    name: str = "unnamed"
    value: int = 0
    global_default: bool = False
    owner: str = ""


@dataclass
class PriorityClassResult:
    priority_class: PriorityClass
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["negative value"]


def check_priority_classes(classes: list) -> list:
    defaults = sum(1 for item in classes if item.global_default)
    results = []
    for item in classes:
        issues = []
        blocked = False
        if item.value < 0:
            issues.append("negative value")
            blocked = True
        if item.value > MAX_VALUE:
            issues.append("value over maximum")
        if defaults > 1 and item.global_default:
            issues.append("duplicate global default")
        if not item.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(PriorityClassResult(item, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# PriorityClass audit", ""]
    lines.append(f"- PriorityClasses checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No PriorityClasses to check.")
        return "\n".join(lines) + "\n"
    lines.append("## PriorityClasses")
    lines.append(
        "| Class | Value | Global default | Owner | Verdict | Issues |"
    )
    lines.append(
        "| ----- | ----- | -------------- | ----- | ------- | ------ |"
    )
    for result in sorted(
        results, key=lambda r: r.priority_class.name
    ):
        item = result.priority_class
        default = "yes" if item.global_default else "no"
        owner = item.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {item.name} | {item.value} | {default} | {owner} "
            f"| {result.verdict} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def priority_classes_from_json(data: list) -> list:
    return [
        PriorityClass(
            name=item.get("name", "unnamed"),
            value=int(item.get("value", 0)),
            global_default=bool(item.get("global_default", False)),
            owner=item.get("owner", ""),
        )
        for item in data
    ]
