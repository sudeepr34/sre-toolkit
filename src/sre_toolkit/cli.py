"""Command line interface for sre-toolkit."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

from .alert_noise import noise_report
from .brief import brief_markdown
from .comms import STATUSES, StatusUpdate, status_page_from_dict
from .handoff import Handoff, handoff_from_dict
from .log_triage import error_rate, summarize
from .postmortem import Postmortem, postmortem_from_dict
from .runbook import db_failover_runbook
from .slo import slo_assessment_from_dict
from .deploy import deploy_gate_from_dict, parse_datetime
from .escalate import escalation_book_from_dict
from .incident import IncidentStore
from .oncall import rotation_from_dict, parse_date
from .review import weekly_review_from_postmortems


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


def _incident_store(args: argparse.Namespace) -> IncidentStore:
    return IncidentStore(args.state)


def cmd_incident_start(args: argparse.Namespace) -> int:
    store = _incident_store(args)
    incident = store.start(
        args.title, severity=args.severity, started=args.started or ""
    )
    print(incident.to_markdown())
    return 0


def cmd_incident_status(args: argparse.Namespace) -> int:
    store = _incident_store(args)
    try:
        incident = store.get(args.id)
        now = parse_datetime(args.now) if args.now else None
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(incident.to_markdown(now))
    return 0


def cmd_incident_note(args: argparse.Namespace) -> int:
    store = _incident_store(args)
    try:
        incident = store.get(args.id)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    incident.add_note(args.message, timestamp=args.at or "")
    store.save()
    print(f"note added to {incident.id}")
    return 0


def cmd_incident_list(args: argparse.Namespace) -> int:
    store = _incident_store(args)
    open_incidents = store.list_open()
    if not open_incidents:
        print("no open incidents")
        return 0
    for incident in open_incidents:
        print(f"{incident.id} [{incident.status}] {incident.title} ({incident.severity})")
    return 0


def cmd_incident_resolve(args: argparse.Namespace) -> int:
    store = _incident_store(args)
    try:
        incident = store.get(args.id)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    incident.resolve(timestamp=args.at or "")
    store.save()
    print(incident.to_markdown())
    return 0


def cmd_incident_set_status(args: argparse.Namespace) -> int:
    store = _incident_store(args)
    try:
        incident = store.get(args.id)
        incident.set_status(args.status)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    store.save()
    print(incident.to_markdown())
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    postmortems = []
    for path in args.files:
        try:
            with open(path) as handle:
                postmortems.append(postmortem_from_dict(json.load(handle)))
        except (ValueError, KeyError, OSError) as exc:
            print(f"error: {path}: {exc}", file=sys.stderr)
            return 2
    review = weekly_review_from_postmortems(postmortems, week=args.week or "")
    print(review.to_markdown())
    return 0


def cmd_oncall(args: argparse.Namespace) -> int:
    try:
        with open(args.rota) as handle:
            rota = rotation_from_dict(json.load(handle))
        moment = parse_date(args.date) if args.date else date.today()
    except (ValueError, KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    try:
        print(rota.to_markdown(moment))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def cmd_escalate(args: argparse.Namespace) -> int:
    try:
        with open(args.policy) as handle:
            book = escalation_book_from_dict(json.load(handle))
        state = book.resolve(args.severity, args.elapsed)
    except (ValueError, KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(state.to_markdown())
    return 0


def cmd_comms(args: argparse.Namespace) -> int:
    if args.file:
        with open(args.file) as handle:
            page = status_page_from_dict(json.load(handle))
        for field in ("title", "severity", "next_update"):
            value = getattr(args, field)
            if value:
                setattr(page, field, value)
        if args.status:
            status = args.status.lower()
            if status not in STATUSES:
                print(
                    f"error: unknown status {args.status!r}; "
                    f"expected one of {', '.join(STATUSES)}",
                    file=sys.stderr,
                )
                return 2
            page.status = status
        if args.message:
            page.updates.append(
                StatusUpdate(
                    timestamp=args.now or "",
                    status=page.status,
                    message=args.message,
                )
            )
    else:
        page = status_page_from_dict(
            {
                "title": args.title or "untitled incident",
                "status": (args.status or "investigating"),
                "severity": args.severity or "SEV-3",
            }
        )
    print(page.to_markdown())
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

    comms = sub.add_parser(
        "comms", help="Draft a customer-facing status page update."
    )
    comms.add_argument(
        "--file",
        default="",
        help="JSON file with title, status, severity, affected, started, "
        "resolved, updates (list of timestamp/status/message), next_update. "
        "Without --file, prints an empty status-page template.",
    )
    comms.add_argument("--title", default=None, help="Incident title.")
    comms.add_argument(
        "--status",
        default=None,
        help="Current status: investigating, identified, monitoring, resolved.",
    )
    comms.add_argument(
        "--severity", default=None, help="Severity, e.g. SEV-2."
    )
    comms.add_argument(
        "--message",
        default=None,
        help="Append a status update with this message (only with --file).",
    )
    comms.add_argument(
        "--now",
        default=None,
        help="Timestamp for the appended update (for testing).",
    )
    comms.add_argument(
        "--next-update", default=None, dest="next_update", help="Next update ETA."
    )
    comms.set_defaults(func=cmd_comms)

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

    escalate = sub.add_parser(
        "escalate", help="Resolve who to page from an escalation policy."
    )
    escalate.add_argument(
        "policy",
        help="JSON escalation book: {'policies': {'SEV-1': {'levels': "
        "[{'wait_minutes': 5, 'targets': ['primary']}, ...]}}, 'default': 'SEV-2'}.",
    )
    escalate.add_argument(
        "--severity",
        default="",
        help="Incident severity, e.g. SEV-1 (default: the book's default policy).",
    )
    escalate.add_argument(
        "--elapsed",
        type=int,
        default=0,
        help="Minutes since the incident started (default 0).",
    )
    escalate.set_defaults(func=cmd_escalate)

    oncall = sub.add_parser(
        "oncall", help="Look up who's on call from a rotation."
    )
    oncall.add_argument(
        "rota",
        help="JSON rotation: {'name': 'backend', 'members': ['priya', ...], "
        "'start_date': 'YYYY-MM-DD', 'shift_days': 7}.",
    )
    oncall.add_argument(
        "--date",
        default=None,
        help="Look up this YYYY-MM-DD date instead of today.",
    )
    oncall.set_defaults(func=cmd_oncall)

    review = sub.add_parser(
        "review", help="Roll up postmortems into a weekly ops review."
    )
    review.add_argument(
        "files",
        nargs="+",
        help="Postmortem JSON files (as written for the postmortem command).",
    )
    review.add_argument(
        "--week", default=None, help="Week label, e.g. 2026-W42."
    )
    review.set_defaults(func=cmd_review)

    incident = sub.add_parser("incident", help="Track live incidents.")
    incident.add_argument(
        "--state",
        default=str(Path.home() / ".sre-toolkit-incidents.json"),
        help="JSON state file for incidents (default ~/.sre-toolkit-incidents.json).",
    )
    inc_sub = incident.add_subparsers(dest="incident_command", required=True)

    inc_start = inc_sub.add_parser("start", help="Start tracking an incident.")
    inc_start.add_argument("--title", required=True, help="Incident title.")
    inc_start.add_argument("--severity", default="SEV-3", help="e.g. SEV-2.")
    inc_start.add_argument("--started", default="", help="ISO start time (for testing).")
    inc_start.set_defaults(func=cmd_incident_start)

    inc_status = inc_sub.add_parser("status", help="Show an incident with elapsed time.")
    inc_status.add_argument("id", help="Incident id, e.g. INC-0001.")
    inc_status.add_argument("--now", default=None, help="ISO time for elapsed (testing).")
    inc_status.set_defaults(func=cmd_incident_status)

    inc_note = inc_sub.add_parser("note", help="Append a timeline note.")
    inc_note.add_argument("id", help="Incident id.")
    inc_note.add_argument("--message", required=True, help="Note text.")
    inc_note.add_argument("--at", default="", help="ISO timestamp (for testing).")
    inc_note.set_defaults(func=cmd_incident_note)

    inc_list = inc_sub.add_parser("list", help="List open incidents.")
    inc_list.set_defaults(func=cmd_incident_list)

    inc_resolve = inc_sub.add_parser("resolve", help="Resolve an incident.")
    inc_resolve.add_argument("id", help="Incident id.")
    inc_resolve.add_argument("--at", default="", help="ISO timestamp (for testing).")
    inc_resolve.set_defaults(func=cmd_incident_resolve)

    inc_set = inc_sub.add_parser("set-status", help="Change incident status.")
    inc_set.add_argument("id", help="Incident id.")
    inc_set.add_argument(
        "--status",
        required=True,
        help="open, acknowledged, mitigating, resolved.",
    )
    inc_set.set_defaults(func=cmd_incident_set_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
