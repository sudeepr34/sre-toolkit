"""Log retention policy checks.

Logs are only useful if they still exist when you need them. This
checks each service's log retention against the policy minimum and
flags the two gaps that bite during incidents: retention shorter than
policy, and retention that was never configured at all. Exit code 1
when any record is non-compliant, for CI gating.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RetentionRecord:
    service: str
    log_type: str = "all"
    retention_days: float | None = None  # None means not configured
    required_days: float = 30.0


@dataclass
class RetentionResult:
    record: RetentionRecord
    status: str  # compliant, shortfall, missing
    detail: str

    @property
    def label(self) -> str:
        return f"{self.record.service}/{self.record.log_type}"


def check_retention(records: list) -> list:
    results = []
    for record in records:
        if record.retention_days is None:
            results.append(
                RetentionResult(record, "missing", "retention not configured")
            )
        elif record.retention_days >= record.required_days:
            results.append(
                RetentionResult(
                    record, "compliant",
                    f"{record.retention_days:g}d retained (policy {record.required_days:g}d)",
                )
            )
        else:
            shortfall = record.required_days - record.retention_days
            results.append(
                RetentionResult(
                    record, "shortfall",
                    f"{record.retention_days:g}d retained, "
                    f"{shortfall:g}d short of policy {record.required_days:g}d",
                )
            )
    return results


def to_markdown(results: list) -> str:
    lines = ["# Retention check", ""]
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    summary = ", ".join(f"{n} {status}" for status, n in sorted(counts.items()))
    lines.append(f"- Checked {len(results)} records: {summary}")
    lines.append("")
    lines.append("| Service / Log | Status | Detail |")
    lines.append("| ------------- | ------ | ------ |")
    for result in results:
        lines.append(f"| {result.label} | {result.status} | {result.detail} |")
    lines.append("")
    problems = [r for r in results if r.status != "compliant"]
    if problems:
        lines.append("## Gaps")
        for result in problems:
            lines.append(f"- {result.label}: {result.detail}")
    else:
        lines.append("All retention meets policy.")
    return "\n".join(lines) + "\n"


def records_from_json(data: list) -> list:
    return [
        RetentionRecord(
            service=item.get("service", "unnamed"),
            log_type=item.get("log_type", "all"),
            retention_days=(
                float(item["retention_days"])
                if item.get("retention_days") is not None else None
            ),
            required_days=float(item.get("required_days", 30)),
        )
        for item in data
    ]
