"""Release cadence.

A service that hasn't shipped in months is either stable or stuck,
and the difference matters. This checks a JSON list of releases and
reports days since the last release per service, flagging the stale
ones, so a stalled pipeline is visible before the next big-bang
release has to land all at once.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class Release:
    version: str
    service: str
    date: str  # ISO date


@dataclass
class ServiceCadence:
    service: str
    last_release: date | None  # None when no date parses
    last_version: str
    days_since: int | None
    stale: bool


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip()[:10])
    except (ValueError, AttributeError):
        return None


def check_releases(releases: list, today: date, stale_days: int = 30) -> list:
    latest: dict[str, Release] = {}
    for release in releases:
        released = _parse_date(release.date)
        if released is None:
            continue
        current = latest.get(release.service)
        if current is None or released > _parse_date(current.date):
            latest[release.service] = release
    results = []
    for service, release in sorted(latest.items()):
        released = _parse_date(release.date)
        days = (today - released).days
        results.append(
            ServiceCadence(service, released, release.version, days, days > stale_days)
        )
    return results


def to_markdown(results: list) -> str:
    stale = [r for r in results if r.stale]
    lines = ["# Release cadence", ""]
    lines.append(f"- Services checked: {len(results)}")
    lines.append(f"- Stale services: {len(stale)}")
    lines.append("")
    if not results:
        lines.append("No releases to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Cadence")
    lines.append("| Service | Last version | Last release | Days since | Stale |")
    lines.append("| ------- | ------------ | ------------ | ---------- | ----- |")
    for result in sorted(results, key=lambda r: -(r.days_since or 0)):
        days = str(result.days_since) if result.days_since is not None else "n/a"
        released = (
            result.last_release.isoformat() if result.last_release else "n/a"
        )
        lines.append(
            f"| {result.service} | {result.last_version} | {released} "
            f"| {days} | {'yes' if result.stale else 'no'} |"
        )
    return "\n".join(lines) + "\n"


def releases_from_json(data: list) -> list:
    return [
        Release(
            version=item.get("version", "unnamed"),
            service=item.get("service", "unnamed"),
            date=item.get("date", ""),
        )
        for item in data
    ]
