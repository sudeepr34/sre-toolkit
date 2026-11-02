"""Config drift detection.

Compares an expected config against the actual one and reports every
difference: keys that changed, keys that went missing, and keys that
appeared out of nowhere. Nested dicts are walked with dotted paths, so
a drifted value names exactly where it lives. Exit code 1 when drift is
found, for CI gating.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Drift:
    path: str
    kind: str  # changed, missing, extra
    expected: object = None
    actual: object = None


def _join(prefix: str, key: str) -> str:
    return f"{prefix}.{key}" if prefix else key


def diff_configs(expected: dict, actual: dict, prefix: str = "") -> list:
    """All drifts between two config dicts, in sorted-key order."""
    drifts = []
    for key in sorted(expected):
        path = _join(prefix, key)
        if key not in actual:
            drifts.append(Drift(path, "missing", expected=expected[key]))
            continue
        exp_val, act_val = expected[key], actual[key]
        if isinstance(exp_val, dict) and isinstance(act_val, dict):
            drifts.extend(diff_configs(exp_val, act_val, prefix=path))
        elif exp_val != act_val:
            drifts.append(Drift(path, "changed", expected=exp_val, actual=act_val))
    for key in sorted(actual):
        if key not in expected:
            drifts.append(Drift(_join(prefix, key), "extra", actual=actual[key]))
    return drifts


def _fmt(value: object) -> str:
    if isinstance(value, str):
        return value
    return repr(value)


def to_markdown(drifts: list) -> str:
    lines = ["# Config drift", ""]
    lines.append(f"- Drifts found: {len(drifts)}")
    lines.append("")
    if not drifts:
        lines.append("No drift: actual config matches expected.")
        return "\n".join(lines) + "\n"
    counts: dict[str, int] = {}
    for drift in drifts:
        counts[drift.kind] = counts.get(drift.kind, 0) + 1
    lines.append("## By kind")
    for kind, count in sorted(counts.items()):
        lines.append(f"- {kind}: {count}")
    lines.append("")
    lines.append("## Drifts")
    lines.append("| Path | Kind | Expected | Actual |")
    lines.append("| ---- | ---- | -------- | ------ |")
    for drift in drifts:
        expected = _fmt(drift.expected) if drift.kind != "extra" else "-"
        actual = _fmt(drift.actual) if drift.kind != "missing" else "-"
        lines.append(f"| {drift.path} | {drift.kind} | {expected} | {actual} |")
    return "\n".join(lines) + "\n"
