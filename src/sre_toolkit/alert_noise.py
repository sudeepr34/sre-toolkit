"""Cut alert noise: fingerprint duplicate alerts, detect flapping."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

# Labels that change on every firing (timestamps, run IDs) and must be
# excluded when deciding whether two alerts are "the same" alert.
VOLATILE_LABELS = frozenset({"timestamp", "run_id", "alert_id", "fingerprint"})


def fingerprint(alert: dict) -> str:
    """Stable identity for an alert: name + sorted non-volatile labels."""
    labels = alert.get("labels", {})
    stable = sorted(f"{k}={v}" for k, v in labels.items() if k not in VOLATILE_LABELS)
    return alert.get("name", "unnamed") + "|" + ",".join(stable)


@dataclass
class AlertGroup:
    fingerprint: str
    name: str
    count: int
    first_seen: str | None = None
    last_seen: str | None = None
    flapping: bool = False


def group_alerts(alerts: list[dict]) -> list[AlertGroup]:
    """Cluster alerts by fingerprint, tracking first/last seen timestamps."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for alert in alerts:
        buckets[fingerprint(alert)].append(alert)
    groups = []
    for fp, items in buckets.items():
        stamps = sorted(a.get("timestamp", "") for a in items if a.get("timestamp"))
        groups.append(
            AlertGroup(
                fingerprint=fp,
                name=items[0].get("name", "unnamed"),
                count=len(items),
                first_seen=stamps[0] if stamps else None,
                last_seen=stamps[-1] if stamps else None,
            )
        )
    return sorted(groups, key=lambda g: g.count, reverse=True)


def detect_flapping(alerts: list[dict], min_transitions: int = 3) -> list[str]:
    """Return fingerprints of alerts that fired AND resolved repeatedly.

    An alert is flapping when its state flips between firing/resolved at
    least ``min_transitions`` times -- the classic pager-fatigue pattern.
    """
    by_fp: dict[str, list[str]] = defaultdict(list)
    for alert in alerts:
        state = alert.get("state", "firing")
        by_fp[fingerprint(alert)].append(state)
    flapping = []
    for fp, states in by_fp.items():
        transitions = sum(1 for a, b in zip(states, states[1:]) if a != b)
        if transitions >= min_transitions:
            flapping.append(fp)
    return flapping


def noise_report(alerts: list[dict], top_n: int = 5) -> dict:
    """Summary a human can paste into an incident channel."""
    groups = group_alerts(alerts)
    flapping = set(detect_flapping(alerts))
    for group in groups:
        group.flapping = group.fingerprint in flapping
    return {
        "total_alerts": len(alerts),
        "unique_fingerprints": len(groups),
        "duplicates_suppressed": len(alerts) - len(groups),
        "flapping": sorted(flapping),
        "top_groups": [
            {"name": g.name, "count": g.count, "flapping": g.flapping}
            for g in groups[:top_n]
        ],
    }
