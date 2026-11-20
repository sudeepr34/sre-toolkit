"""ConfigMap audit.

A ConfigMap with no data keys is a mount that delivers nothing,
and one over the 1MiB etcd limit cannot be stored at all — the
workload that depends on it fails at apply time, not at runtime.
This checks a JSON list of ConfigMaps (key counts and sizes only,
never values) and flags the ones that are empty, oversized, or
have no owner, so the config is fixed before the next rollout
reads it.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConfigMap:
    name: str = "unnamed"
    namespace: str = "default"
    keys: int = 0
    empty_keys: int = 0
    size_kb: int = 0
    owner: str = ""


@dataclass
class ConfigMapResult:
    config_map: ConfigMap
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["no data keys"]


def check_config_maps(maps: list) -> list:
    results = []
    for item in maps:
        issues = []
        blocked = False
        if item.keys == 0:
            issues.append("no data keys")
            blocked = True
        if item.size_kb > 1024:
            issues.append("exceeds 1MiB limit")
            blocked = True
        if item.empty_keys > 0:
            issues.append("empty values")
        if 512 < item.size_kb <= 1024:
            issues.append("large configmap")
        if not item.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(ConfigMapResult(item, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# ConfigMap audit", ""]
    lines.append(f"- ConfigMaps checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No ConfigMaps to check.")
        return "\n".join(lines) + "\n"
    lines.append("## ConfigMaps")
    lines.append(
        "| Namespace | ConfigMap | Keys | Empty keys | Size (KiB) "
        "| Owner | Verdict | Issues |"
    )
    lines.append(
        "| --------- | --------- | ---- | ---------- | ---------- "
        "| ----- | ------- | ------ |"
    )
    for result in sorted(
        results, key=lambda r: (r.config_map.namespace, r.config_map.name)
    ):
        item = result.config_map
        owner = item.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {item.namespace} | {item.name} | {item.keys} "
            f"| {item.empty_keys} | {item.size_kb} | {owner} "
            f"| {result.verdict} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def config_maps_from_json(data: list) -> list:
    return [
        ConfigMap(
            name=item.get("name", "unnamed"),
            namespace=item.get("namespace", "default"),
            keys=int(item.get("keys", 0)),
            empty_keys=int(item.get("empty_keys", 0)),
            size_kb=int(item.get("size_kb", 0)),
            owner=item.get("owner", ""),
        )
        for item in data
    ]
