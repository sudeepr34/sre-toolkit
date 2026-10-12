"""Command line interface for sre-toolkit."""
from __future__ import annotations

import argparse
import json
import sys

from .alert_noise import noise_report
from .handoff import Handoff, handoff_from_dict
from .log_triage import error_rate, summarize
from .runbook import db_failover_runbook


def cmd_logs(args: argparse.Namespace) -> int:
    with open(args.file) as handle:
        summary = summarize(handle, top_n=args.top)
    print(f"lines: {summary.total} (parsed {summary.parsed})")
    print("by level:")
    for level, count in sorted(summary.by_level.items()):
        print(f"  {level}: {count}")
    print(f"error rate: {error_rate(summary):.1%}")
    if summary.top_errors:
        print("top errors:")
        for message, count in summary.top_errors:
            print(f"  [{count}x] {message[:120]}")
    return 0


def cmd_alerts(args: argparse.Namespace) -> int:
    with open(args.file) as handle:
        alerts = json.load(handle)
    report = noise_report(alerts, top_n=args.top)
    print(
        f"total alerts: {report['total_alerts']} "
        f"({report['unique_fingerprints']} unique)"
    )
    print(f"duplicates suppressed: {report['duplicates_suppressed']}")
    if report["flapping"]:
        print("flapping:")
        for fp in report["flapping"]:
            print(f"  {fp}")
    if report["top_groups"]:
        print("top groups:")
        for group in report["top_groups"]:
            flap = " [FLAPPING]" if group["flapping"] else ""
            print(f"  [{group['count']}x] {group['name']}{flap}")
    return 0


def cmd_runbook(args: argparse.Namespace) -> int:
    runbook = db_failover_runbook()
    if args.complete:
        for raw in args.complete.split(","):
            runbook.complete(int(raw.strip()) - 1)
    print(runbook.to_markdown())
    nxt = runbook.next_step
    if nxt is not None:
        print(f"\nnext step: {nxt.title} (owner: {nxt.owner})")
    return 0


def cmd_handoff(args: argparse.Namespace) -> int:
    if args.file:
        with open(args.file) as handle:
            handoff = handoff_from_dict(json.load(handle))
        for field in ("shift", "outgoing", "incoming"):
            value = getattr(args, field)
            if value:
                setattr(handoff, field, value)
    else:
        handoff = Handoff(
            shift=args.shift or "",
            outgoing=args.outgoing or "on-call",
            incoming=args.incoming or "on-call",
        )
    print(handoff.to_markdown())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sre-toolkit", description="Small CLI utilities for on-call SRE work."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    logs = sub.add_parser("logs", help="Triage a log file.")
    logs.add_argument("file", help="Path to the log file.")
    logs.add_argument("--top", type=int, default=5, help="Top error messages to show.")
    logs.set_defaults(func=cmd_logs)

    alerts = sub.add_parser("alerts", help="Analyze alert noise.")
    alerts.add_argument(
        "file", help="Path to a JSON file containing a list of alerts."
    )
    alerts.add_argument(
        "--top", type=int, default=5, help="Top alert groups to show."
    )
    alerts.set_defaults(func=cmd_alerts)

    runbook = sub.add_parser("runbook", help="Print an incident runbook checklist.")
    runbook.add_argument(
        "--complete",
        default="",
        help="Comma-separated 1-based step numbers to mark done (e.g. --complete 1,2).",
    )
    runbook.set_defaults(func=cmd_runbook)

    handoff = sub.add_parser("handoff", help="Generate on-call handoff notes.")
    handoff.add_argument(
        "--file",
        default="",
        help="JSON file with handoff sections (shift, outgoing, incoming, "
        "open_incidents, watch_items, follow_ups, recent_changes). Without "
        "--file, prints an empty handoff template for the shift.",
    )
    handoff.add_argument("--shift", default=None, help="Shift label, e.g. 2026-10-12.")
    handoff.add_argument("--outgoing", default=None, help="Outgoing on-call.")
    handoff.add_argument("--incoming", default=None, help="Incoming on-call.")
    handoff.set_defaults(func=cmd_handoff)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
