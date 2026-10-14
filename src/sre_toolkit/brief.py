"""Start-of-shift brief: one page answering "what's my shift walking into?"

Composes the alert noise report and the previous shift's handoff into a
single Markdown page: how noisy the last window was, what's flapping, and
which incidents, watch items and follow-ups carry over to this shift.
"""
from __future__ import annotations

from .alert_noise import noise_report
from .handoff import Handoff

_SEVERITY_ORDER = {"SEV-1": 0, "SEV-2": 1, "SEV-3": 2, "SEV-4": 3}


def _severity_rank(severity: str) -> int:
    return _SEVERITY_ORDER.get(severity.upper(), 4)


def brief_markdown(
    alerts: list[dict],
    handoff: Handoff | None = None,
    shift: str = "",
    top_n: int = 5,
) -> str:
    """Render the shift brief as Markdown.

    ``alerts`` is the raw alert list (same shape ``alerts`` takes).
    ``handoff`` is optional: the previous shift's Handoff for carryover.
    """
    report = noise_report(alerts, top_n=top_n)
    lines = [f"# Shift brief: {shift or 'this shift'}", ""]

    lines.append("## Alert noise")
    lines.append(
        f"- Total: {report['total_alerts']} "
        f"({report['unique_fingerprints']} unique)"
    )
    lines.append(f"- Duplicates suppressed: {report['duplicates_suppressed']}")
    flapping = report["flapping"]
    if flapping:
        shown = ", ".join(flapping[:top_n])
        extra = f" (+{len(flapping) - top_n} more)" if len(flapping) > top_n else ""
        lines.append(f"- Flapping ({len(flapping)}): {shown}{extra}")
    else:
        lines.append("- Flapping: none")
    if report["top_groups"]:
        lines.append("- Top groups:")
        for group in report["top_groups"]:
            flap = " [FLAPPING]" if group["flapping"] else ""
            lines.append(f"  - [{group['count']}x] {group['name']}{flap}")

    if handoff is not None:
        lines.append("")
        lines.append("## Carried over")
        open_incidents = [
            i for i in handoff.open_incidents if i.status != "resolved"
        ]
        lines.append(f"### Open incidents ({len(open_incidents)})")
        for incident in sorted(
            open_incidents, key=lambda i: _severity_rank(i.severity)
        ):
            lines.append(
                f"- **{incident.severity}** {incident.title} "
                f"({incident.status}, owner: {incident.owner})"
            )
        if not open_incidents:
            lines.append("- none")
        lines.append(f"### Watch items ({len(handoff.watch_items)})")
        if handoff.watch_items:
            lines.extend(f"- {item}" for item in handoff.watch_items)
        else:
            lines.append("- none")
        lines.append(f"### Follow-ups ({len(handoff.follow_ups)})")
        if handoff.follow_ups:
            for follow_up in handoff.follow_ups:
                due = f" (due: {follow_up.due})" if follow_up.due else ""
                lines.append(f"- [ ] {follow_up.task} — {follow_up.owner}{due}")
        else:
            lines.append("- none")

    return "\n".join(lines) + "\n"
