"""Database migration status.

A pending migration is a schema change someone meant to ship, and a
failed one is a deploy that already went sideways. This checks a JSON
list of migrations and reports the pending, failed, and stale-pending
ones, so the migration backlog is visible before it blocks the next
release.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class Migration:
    id: str
    service: str
    status: str  # applied, pending, failed
    created: str = ""  # ISO date the migration was written
    applied_at: str = ""  # ISO date it was applied


@dataclass
class MigrationResult:
    migration: Migration
    days_pending: int | None  # None when the created date won't parse
    stale: bool  # pending longer than the stale threshold


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip()[:10])
    except (ValueError, AttributeError):
        return None


def check_migrations(migrations: list, today: date, stale_days: int = 14) -> list:
    results = []
    for migration in migrations:
        created = _parse_date(migration.created)
        if migration.status.lower() == "pending" and created is not None:
            days = (today - created).days
            stale = days > stale_days
        else:
            days = None
            stale = False
        results.append(MigrationResult(migration, days, stale))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.migration.status.lower()] = (
            counts.get(result.migration.status.lower(), 0) + 1
        )
    pending = [r for r in results if r.migration.status.lower() == "pending"]
    failed = [r for r in results if r.migration.status.lower() == "failed"]
    stale = [r for r in pending if r.stale]
    lines = ["# Migration status", ""]
    lines.append(f"- Migrations checked: {len(results)}")
    lines.append(f"- Applied: {counts.get('applied', 0)}")
    lines.append(f"- Pending: {len(pending)}")
    lines.append(f"- Failed: {len(failed)}")
    lines.append(f"- Stale pending: {len(stale)}")
    lines.append("")
    if not pending and not failed:
        lines.append("Clean: every migration is applied, nothing pending or failed.")
        return "\n".join(lines) + "\n"
    lines.append("## Attention")
    lines.append("| ID | Service | Status | Days pending |")
    lines.append("| -- | ------- | ------ | ------------ |")
    status_rank = {"failed": 0, "pending": 1}
    for result in sorted(
        pending + failed,
        key=lambda r: (status_rank.get(r.migration.status.lower(), 2),
                       -(r.days_pending or 0)),
    ):
        days = str(result.days_pending) if result.days_pending is not None else "n/a"
        lines.append(
            f"| {result.migration.id} | {result.migration.service} "
            f"| {result.migration.status} | {days} |"
        )
    return "\n".join(lines) + "\n"


def migrations_from_json(data: list) -> list:
    return [
        Migration(
            id=item.get("id", "unnamed"),
            service=item.get("service", "unnamed"),
            status=item.get("status", "pending"),
            created=item.get("created", ""),
            applied_at=item.get("applied_at", ""),
        )
        for item in data
    ]
