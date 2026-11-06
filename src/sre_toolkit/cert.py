"""TLS certificate expiry checks.

Expired certificates are one of the most embarrassing ways to page
someone at 3 a.m. This checks a JSON list of certificates against
warn and critical day thresholds, so renewals land on a checklist
instead of an outage.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class CertRecord:
    host: str
    expires: str  # ISO date or datetime
    issuer: str = ""


@dataclass
class CertResult:
    record: CertRecord
    days_left: float | None  # None when the expiry date won't parse
    status: str  # ok, warn, critical, expired, unknown


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip()[:10])
    except (ValueError, AttributeError):
        return None


def check_certs(
    records: list,
    today: date,
    warn_days: int = 30,
    critical_days: int = 7,
) -> list:
    results = []
    for record in records:
        expires = _parse_date(record.expires)
        if expires is None:
            results.append(CertResult(record, None, "unknown"))
            continue
        days = (expires - today).days
        if days < 0:
            status = "expired"
        elif days < critical_days:
            status = "critical"
        elif days < warn_days:
            status = "warn"
        else:
            status = "ok"
        results.append(CertResult(record, float(days), status))
    return results


def attention_needed(results: list) -> bool:
    return any(r.status in ("critical", "expired", "unknown") for r in results)


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    lines = ["# Certificate expiry check", ""]
    lines.append(f"- Certificates checked: {len(results)}")
    lines.append(f"- Expired: {counts.get('expired', 0)}")
    lines.append(f"- Critical: {counts.get('critical', 0)}")
    lines.append(f"- Warn: {counts.get('warn', 0)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    if counts.get("unknown"):
        lines.append(f"- Unknown: {counts['unknown']}")
    lines.append("")
    if not results:
        lines.append("No certificates to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Certificates")
    lines.append("| Host | Expires | Days left | Status |")
    lines.append("| ---- | ------- | --------- | ------ |")
    for result in results:
        days = (
            f"{result.days_left:.0f}"
            if result.days_left is not None
            else "n/a"
        )
        lines.append(
            f"| {result.record.host} | {result.record.expires} "
            f"| {days} | {result.status} |"
        )
    return "\n".join(lines) + "\n"


def records_from_json(data: list) -> list:
    return [
        CertRecord(
            host=item.get("host", "unnamed"),
            expires=item.get("expires", ""),
            issuer=item.get("issuer", ""),
        )
        for item in data
    ]
