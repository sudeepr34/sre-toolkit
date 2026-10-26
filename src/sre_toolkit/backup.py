"""Backup verification.

Checks each service's backups against its expected cadence and flags
two failure modes SREs actually miss: backups that stopped arriving,
and restores that were never tested. Feed it a JSON list of records and
it prints a report naming what's stale.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

RESTORE_TEST_MAX_DAYS = 30


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))


@dataclass
class BackupRecord:
    service: str
    last_backup: str = ""  # ISO timestamp; empty means no backup recorded
    cadence_hours: float = 24.0
    last_restore_test: str = ""  # ISO date/timestamp; empty means never tested

    def backup_age_hours(self, now: datetime) -> float | None:
        """Hours since the last backup; None when no backup is recorded."""
        if not self.last_backup:
            return None
        try:
            return max(0.0, (now - _parse_ts(self.last_backup)).total_seconds() / 3600)
        except ValueError:
            return None

    def restore_test_age_days(self, now: datetime) -> float | None:
        """Days since the last restore test; None when never tested."""
        if not self.last_restore_test:
            return None
        try:
            return max(0.0, (now - _parse_ts(self.last_restore_test)).total_seconds() / 86400)
        except ValueError:
            return None


@dataclass
class BackupResult:
    record: BackupRecord
    status: str  # ok, stale, never, restore-stale
    detail: str

    @property
    def service(self) -> str:
        return self.record.service


def check_backups(
    records: list,
    now: datetime | None = None,
    restore_max_days: int = RESTORE_TEST_MAX_DAYS,
) -> list:
    """Evaluate each record. Worst status wins: never > stale > restore-stale."""
    moment = now or datetime.now()
    results = []
    for record in records:
        age = record.backup_age_hours(moment)
        if age is None:
            results.append(BackupResult(record, "never", "no backup recorded"))
            continue
        if age > record.cadence_hours:
            results.append(
                BackupResult(
                    record, "stale",
                    f"last backup {age:.1f}h ago, cadence is {record.cadence_hours:g}h",
                )
            )
            continue
        restore_age = record.restore_test_age_days(moment)
        if restore_age is None:
            results.append(BackupResult(record, "restore-stale", "restore never tested"))
        elif restore_age > restore_max_days:
            results.append(
                BackupResult(
                    record, "restore-stale",
                    f"last restore test {restore_age:.0f}d ago (max {restore_max_days}d)",
                )
            )
        else:
            results.append(
                BackupResult(record, "ok", f"last backup {age:.1f}h ago")
            )
    return results


def to_markdown(results: list) -> str:
    lines = ["# Backup verification", ""]
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    summary = ", ".join(f"{n} {status}" for status, n in sorted(counts.items()))
    lines.append(f"- Checked {len(results)} services: {summary}")
    lines.append("")
    lines.append("| Service | Status | Detail |")
    lines.append("| ------- | ------ | ------ |")
    for result in results:
        lines.append(f"| {result.service} | {result.status} | {result.detail} |")
    lines.append("")
    problems = [r for r in results if r.status != "ok"]
    if problems:
        lines.append("## Needs attention")
        for result in problems:
            lines.append(f"- {result.service}: {result.detail}")
    else:
        lines.append("All backups fresh and restore tests current.")
    return "\n".join(lines) + "\n"


def records_from_json(data: list) -> list:
    return [
        BackupRecord(
            service=item.get("service", "unnamed"),
            last_backup=item.get("last_backup", ""),
            cadence_hours=float(item.get("cadence_hours", 24)),
            last_restore_test=item.get("last_restore_test", ""),
        )
        for item in data
    ]
