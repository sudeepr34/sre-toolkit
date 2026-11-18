"""Cron schedule audit.

A CronJob with a mistyped schedule never runs — or runs every
minute and hammers the cluster at 3 a.m. This checks a JSON list
of cron schedules and flags the ones that are invalid, too
frequent, or duplicated, so the schedule is fixed — or the extra
job removed — before the next missed backup or thundering herd.
"""
from __future__ import annotations

from dataclasses import dataclass

MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
DOW_NAMES = {
    "sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6,
}

# (min, max, names) per field: minute, hour, day-of-month, month, day-of-week
FIELDS = (
    (0, 59, None),
    (0, 23, None),
    (1, 31, None),
    (1, 12, MONTH_NAMES),
    (0, 7, DOW_NAMES),
)


@dataclass
class CronSchedule:
    name: str = "unnamed"
    namespace: str = "default"
    schedule: str = ""
    owner: str = ""


@dataclass
class CronResult:
    cron: CronSchedule
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["invalid schedule"]


def _value_ok(value: str, low: int, high: int, names: dict | None) -> bool:
    if names and value.lower() in names:
        return True
    if not value.isdigit():
        return False
    return low <= int(value) <= high


def _base_ok(base: str, low: int, high: int, names: dict | None) -> bool:
    if base == "*":
        return True
    if "-" in base:
        start, end = base.split("-", 1)
        return _value_ok(start, low, high, names) and _value_ok(
            end, low, high, names
        )
    return _value_ok(base, low, high, names)


def _field_ok(field: str, low: int, high: int, names: dict | None) -> bool:
    for part in field.split(","):
        if not part:
            return False
        if "/" in part:
            base, step = part.split("/", 1)
            if not step.isdigit() or int(step) < 1:
                return False
            if not _base_ok(base, low, high, names):
                return False
        elif not _base_ok(part, low, high, names):
            return False
    return True


def is_valid_schedule(schedule: str) -> bool:
    fields = schedule.split()
    if len(fields) != 5:
        return False
    return all(
        _field_ok(field, low, high, names)
        for field, (low, high, names) in zip(fields, FIELDS)
    )


def _runs_every_minute(schedule: str) -> bool:
    minute = schedule.split()[0]
    return minute in ("*", "*/1")


def check_crons(crons: list) -> list:
    seen: dict[tuple, int] = {}
    for cron in crons:
        key = (cron.namespace, cron.schedule)
        seen[key] = seen.get(key, 0) + 1
    results = []
    for cron in crons:
        issues = []
        blocked = False
        if not cron.schedule:
            issues.append("no schedule")
            blocked = True
        elif not is_valid_schedule(cron.schedule):
            issues.append("invalid schedule")
            blocked = True
        else:
            if _runs_every_minute(cron.schedule):
                issues.append("runs every minute")
            if cron.schedule and seen[(cron.namespace, cron.schedule)] > 1:
                issues.append("duplicate schedule")
        if not cron.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(CronResult(cron, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# Cron schedule audit", ""]
    lines.append(f"- Schedules checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No schedules to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Schedules")
    lines.append("| Namespace | Cron | Schedule | Owner | Verdict | Issues |")
    lines.append("| --------- | ---- | -------- | ----- | ------- | ------ |")
    for result in sorted(
        results, key=lambda r: (r.cron.namespace, r.cron.name)
    ):
        cron = result.cron
        schedule = cron.schedule or "—"
        owner = cron.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {cron.namespace} | {cron.name} | {schedule} | {owner} "
            f"| {result.verdict} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def crons_from_json(data: list) -> list:
    return [
        CronSchedule(
            name=item.get("name", "unnamed"),
            namespace=item.get("namespace", "default"),
            schedule=item.get("schedule", ""),
            owner=item.get("owner", ""),
        )
        for item in data
    ]
