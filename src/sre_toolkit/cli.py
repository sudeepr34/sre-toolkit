"""Command line interface for sre-toolkit."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from .alert_noise import noise_report
from .brief import brief_markdown
from .handoff import Handoff, handoff_from_dict
from .log_triage import error_rate, summarize
from .postmortem import Postmortem, postmortem_from_dict
from .runbook import db_failover_runbook
from .slo import slo_assessment_from_dict
from .deploy import deploy_gate_from_dict, parse_datetime


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


def cmd_postmortem(args: argparse.Namespace) -> int:
    if args.file:
        with open(args.file) as handle:
            postmortem = postmortem_from_dict(json.load(handle))
        for field in ("title", "date", "severity"):
            value = getattr(args, field)
            if value:
                setattr(postmortem, field, value)
    else:
        postmortem = Postmortem(
            title=args.title or "untitled incident",
            date=args.date or "",
            severity=args.severity or "SEV-3",
        )
    print(postmortem.to_markdown())
    return 0


def cmd_deploy(args: argparse.Namespace) -> int:
    """Exit 0 when deploys are allowed, 1 when blocked, 2 on input error."""
    try:
        moment = parse_datetime(args.now) if args.now else datetime.now()
    except ValueError as exc:
        print(f"error: bad --now value: {exc}", file=sys.stderr)
        return 2
    try:
        if args.freezes:
            with open(args.freezes) as handle:
                gate = deploy_gate_from_dict(json.load(handle))
        else:
            gate = deploy_gate_from_dict({})
    except (ValueError, KeyError) as exc:
        print(f"error: bad freeze calendar: {exc}", file=sys.stderr)
        return 2
    result = gate.check(moment)
    print(result.to_markdown())
    return 0 if result.allowed else 1


def cmd_slo(args: argparse.Namespace) -> int:
    data: dict = {}
    if args.file:
        with open(args.file) as handle:
            data = json.load(handle)
    if args.target is not None:
        data["slo_target"] = args.target / 100
    if args.error_rate is not None:
        data["observed_error_ratio"] = args.error_rate / 100
    if args.window_hours is not None:
        data["window_hours"] = args.window_hours
    if args.elapsed_hours is not None:
        data["elapsed_hours"] = args.elapsed_hours
    try:
        assessment = slo_assessment_from_dict(data)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(assessment.to_markdown())
    return 0


def cmd_brief(args: argparse.Namespace) -> int:
    with open(args.alerts) as handle:
        alerts = json.load(handle)
    handoff = None
    if args.handoff:
        with open(args.handoff) as handle:
            handoff = handoff_from_dict(json.load(handle))
    print(brief_markdown(alerts, handoff=handoff, shift=args.shift or ""))
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

    brief = sub.add_parser(
        "brief", help="Render a start-of-shift brief from alerts + last handoff."
    )
    brief.add_argument(
        "alerts", help="Path to a JSON file containing a list of alerts."
    )
    brief.add_argument(
        "--handoff",
        default="",
        help="JSON handoff file from the previous shift, for the carryover "
        "section (open incidents, watch items, follow-ups).",
    )
    brief.add_argument("--shift", default=None, help="Shift label, e.g. 2026-10-13.")
    brief.set_defaults(func=cmd_brief)

    postmortem = sub.add_parser(
        "postmortem",
        help="Generate a blameless postmortem from an incident timeline.",
    )
    postmortem.add_argument(
        "--file",
        default="",
        help="JSON file with postmortem sections (title, date, severity, "
        "summary, timeline, contributing_factors, went_well, action_items). "
        "Without --file, prints an empty postmortem template.",
    )
    postmortem.add_argument("--title", default=None, help="Incident title.")
    postmortem.add_argument("--date", default=None, help="Incident date.")
    postmortem.add_argument(
        "--severity", default=None, help="Severity, e.g. SEV-1."
    )
    postmortem.set_defaults(func=cmd_postmortem)

    slo = sub.add_parser(
        "slo", help="Assess SLO burn rate and error budget."
    )
    slo.add_argument(
        "--file",
        default="",
        help="JSON file with slo_target, observed_error_ratio (as fractions), "
        "window_hours, elapsed_hours. CLI flags override the file.",
    )
    slo.add_argument(
        "--target", type=float, default=None, help="SLO target in percent, e.g. 99.9."
    )
    slo.add_argument(
        "--error-rate",
        type=float,
        default=None,
        help="Observed error ratio in percent, e.g. 0.5.",
    )
    slo.add_argument(
        "--window-hours",
        type=float,
        default=None,
        help="Compliance window in hours (default 720).",
    )
    slo.add_argument(
        "--elapsed-hours",
        type=float,
        default=None,
        help="Hours elapsed in the window (default: the whole window).",
    )
    slo.set_defaults(func=cmd_slo)

    deploy = sub.add_parser(
        "deploy", help="Check the change-freeze gate before deploying."
    )
    deploy.add_argument(
        "--freezes",
        default="",
        help="JSON freeze calendar: {'freezes': [{'kind': 'explicit', 'name', "
        "'start', 'end', 'reason'} | {'kind': 'weekly', 'name', 'weekday', "
        "'start_time', 'end_weekday', 'end_time', 'reason'}]}. Without it, "
        "no gates apply.",
    )
    deploy.add_argument(
        "--now",
        default=None,
        help="Evaluate at this ISO datetime instead of now (for testing).",
    )
    deploy.set_defaults(func=cmd_deploy)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
