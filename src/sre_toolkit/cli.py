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
from .backup import check_backups, records_from_json, to_markdown
from .cost import (
    records_from_json as cost_records_from_json,
    to_markdown as cost_to_markdown,
)
from .audit import diff_configs, to_markdown as audit_to_markdown
from .canary import CanaryAnalysis
from .dora import (
    in_window,
    records_from_json as dora_records_from_json,
    to_markdown as dora_to_markdown,
)
from .health import checks_from_json as health_checks_from_json
from .health import to_markdown as health_to_markdown
from .health import overall_status
from .service import (
    audit_services,
    services_from_json,
    to_markdown as service_to_markdown,
)
from .probe import probe_url, to_markdown as probe_to_markdown
from .queue import (
    check_queues,
    snapshots_from_json as queue_snapshots_from_json,
    to_markdown as queue_to_markdown,
)
from .rollout import (
    check_rollouts,
    rollouts_from_json,
    to_markdown as rollout_to_markdown,
)
from .retention import (
    check_retention,
    records_from_json as retention_records_from_json,
    to_markdown as retention_to_markdown,
)
from .dependency import graph_from_json
from .monitor import lint_rules, rules_from_json, to_markdown as monitor_to_markdown
from .toil import entries_from_json as toil_entries_from_json
from .toil import to_markdown as toil_to_markdown
from .capacity import CapacityPlan
from .drill import get_scenario, list_scenarios
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


def cmd_dora_report(args: argparse.Namespace) -> int:
    try:
        with open(args.deploys) as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        print(f"error: cannot read {args.deploys}: {exc}", file=sys.stderr)
        return 2
    try:
        until = date.fromisoformat(args.until) if args.until else date.today()
        start = (
            date.fromisoformat(args.since)
            if args.since
            else date.fromordinal(until.toordinal() - 27)
        )
    except ValueError as exc:
        print(f"error: bad date: {exc}", file=sys.stderr)
        return 2
    records = in_window(dora_records_from_json(data), start, until)
    print(dora_to_markdown(records, start, until))
    return 0


def cmd_service_audit(args: argparse.Namespace) -> int:
    try:
        with open(args.services) as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        print(f"error: cannot read {args.services}: {exc}", file=sys.stderr)
        return 2
    services = services_from_json(data)
    issues = audit_services(services)
    print(service_to_markdown(services, issues))
    return 1 if issues else 0


def cmd_health_rollup(args: argparse.Namespace) -> int:
    try:
        with open(args.checks) as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        print(f"error: cannot read {args.checks}: {exc}", file=sys.stderr)
        return 2
    checks = health_checks_from_json(data)
    print(health_to_markdown(checks))
    return 1 if overall_status(checks) != "up" else 0


def cmd_probe_check(args: argparse.Namespace) -> int:
    results = [
        probe_url(
            url,
            expected_status=args.expect,
            max_latency_ms=args.max_latency_ms,
            timeout=args.timeout,
        )
        for url in args.urls
    ]
    print(probe_to_markdown(results))
    return 1 if any(r.status == "fail" for r in results) else 0


def cmd_canary_analyze(args: argparse.Namespace) -> int:
    analysis = CanaryAnalysis(
        canary_error_rate=args.canary_error_rate,
        baseline_error_rate=args.baseline_error_rate,
        canary_p99_ms=args.canary_p99,
        baseline_p99_ms=args.baseline_p99,
        canary_requests=args.canary_requests,
        max_error_delta=args.max_error_delta,
        max_p99_ratio=args.max_p99_ratio,
        min_requests=args.min_requests,
    )
    print(analysis.to_markdown())
    return 0 if analysis.verdict() == "promote" else 1


def cmd_rollout_check(args: argparse.Namespace) -> int:
    try:
        with open(args.rollouts) as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        print(f"error: cannot read {args.rollouts}: {exc}", file=sys.stderr)
        return 2
    now = parse_datetime(args.now) if args.now else None
    results = check_rollouts(rollouts_from_json(data), now=now)
    print(rollout_to_markdown(results))
    return 1 if any(r.status != "ok" for r in results) else 0


def cmd_queue_check(args: argparse.Namespace) -> int:
    try:
        with open(args.queues) as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        print(f"error: cannot read {args.queues}: {exc}", file=sys.stderr)
        return 2
    results = check_queues(queue_snapshots_from_json(data))
    print(queue_to_markdown(results))
    return 1 if any(r.status == "breach" for r in results) else 0


def cmd_retention_check(args: argparse.Namespace) -> int:
    try:
        with open(args.retention) as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        print(f"error: cannot read {args.retention}: {exc}", file=sys.stderr)
        return 2
    results = check_retention(retention_records_from_json(data))
    print(retention_to_markdown(results))
    return 1 if any(r.status != "compliant" for r in results) else 0


def cmd_audit_diff(args: argparse.Namespace) -> int:
    try:
        with open(args.expected) as handle:
            expected = json.load(handle)
        with open(args.actual) as handle:
            actual = json.load(handle)
    except (OSError, ValueError) as exc:
        print(f"error: cannot read configs: {exc}", file=sys.stderr)
        return 2
    drifts = diff_configs(expected, actual)
    print(audit_to_markdown(drifts))
    return 1 if drifts else 0


def cmd_monitor_lint(args: argparse.Namespace) -> int:
    try:
        with open(args.rules) as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        print(f"error: cannot read {args.rules}: {exc}", file=sys.stderr)
        return 2
    rules = rules_from_json(data)
    issues = lint_rules(rules)
    print(monitor_to_markdown(rules, issues))
    return 1 if issues else 0


def cmd_deps_report(args: argparse.Namespace) -> int:
    try:
        with open(args.graph) as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        print(f"error: cannot read {args.graph}: {exc}", file=sys.stderr)
        return 2
    graph = graph_from_json(data)
    try:
        if args.service:
            print(graph.service_markdown(args.service))
        else:
            print(graph.full_markdown())
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def cmd_toil_report(args: argparse.Namespace) -> int:
    try:
        with open(args.toil) as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        print(f"error: cannot read {args.toil}: {exc}", file=sys.stderr)
        return 2
    print(
        toil_to_markdown(
            toil_entries_from_json(data),
            capacity_minutes=args.capacity_minutes,
            min_minutes=args.threshold,
        )
    )
    return 0


def cmd_cost_report(args: argparse.Namespace) -> int:
    try:
        with open(args.costs) as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        print(f"error: cannot read {args.costs}: {exc}", file=sys.stderr)
        return 2
    budgets = None
    if args.budgets:
        try:
            with open(args.budgets) as handle:
                budgets = json.load(handle)
        except (OSError, ValueError) as exc:
            print(f"error: cannot read {args.budgets}: {exc}", file=sys.stderr)
            return 2
    print(
        cost_to_markdown(
            cost_records_from_json(data),
            budgets=budgets,
            month=args.month or "",
            prev_month=args.prev_month or "",
            top_n=args.top,
        )
    )
    return 0


def cmd_backup_check(args: argparse.Namespace) -> int:
    try:
        with open(args.backups) as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        print(f"error: cannot read {args.backups}: {exc}", file=sys.stderr)
        return 2
    now = parse_datetime(args.now) if args.now else None
    results = check_backups(
        records_from_json(data), now=now,
        restore_max_days=args.restore_max_days,
    )
    print(to_markdown(results))
    return 0


def cmd_drill_list(args: argparse.Namespace) -> int:
    for scenario in list_scenarios():
        print(
            f"{scenario.id} - {scenario.title} "
            f"({scenario.duration_minutes} min, {scenario.blast_radius})"
        )
    return 0


def cmd_drill_show(args: argparse.Namespace) -> int:
    try:
        scenario = get_scenario(args.id)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(scenario.to_markdown())
    return 0


def cmd_drill_run(args: argparse.Namespace) -> int:
    try:
        scenario = get_scenario(args.id)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(scenario.run_sheet(run_date=args.date or ""))
    return 0


def cmd_capacity(args: argparse.Namespace) -> int:
    try:
        plan = CapacityPlan(
            current_load=args.current_load,
            capacity=args.capacity,
            growth_rate=args.growth,
            target_utilization=args.target,
            periods=args.periods,
            unit=args.unit,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(plan.to_markdown())
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

    capacity = sub.add_parser(
        "capacity", help="Project load growth against capacity."
    )
    cap_forecast = capacity.add_subparsers(dest="capacity_command", required=True)
    cap_f = cap_forecast.add_parser(
        "forecast", help="Print the utilization forecast table."
    )
    cap_f.add_argument("--current-load", type=float, required=True, help="Load now.")
    cap_f.add_argument("--capacity", type=float, required=True, help="Capacity now.")
    cap_f.add_argument(
        "--growth", type=float, required=True,
        help="Growth per period as a fraction, e.g. 0.05 for 5%.",
    )
    cap_f.add_argument(
        "--target", type=float, default=0.70,
        help="Target utilization ceiling (default 0.70).",
    )
    cap_f.add_argument(
        "--periods", type=int, default=12, help="Periods to project (default 12).",
    )
    cap_f.add_argument("--unit", default="rps", help="Load unit label (default rps).")
    cap_f.set_defaults(func=cmd_capacity)

    drill = sub.add_parser("drill", help="Game-day exercise plans.")
    drill_sub = drill.add_subparsers(dest="drill_command", required=True)

    drill_list = drill_sub.add_parser("list", help="List available scenarios.")
    drill_list.set_defaults(func=cmd_drill_list)

    drill_show = drill_sub.add_parser("show", help="Show a scenario's plan.")
    drill_show.add_argument("id", help="Scenario id, e.g. db-failover.")
    drill_show.set_defaults(func=cmd_drill_show)

    drill_run = drill_sub.add_parser("run", help="Print a dated run sheet.")
    drill_run.add_argument("id", help="Scenario id.")
    drill_run.add_argument("--date", default="", help="Run date (default today).")
    drill_run.set_defaults(func=cmd_drill_run)

    backup = sub.add_parser("backup", help="Verify backup freshness.")
    backup_sub = backup.add_subparsers(dest="backup_command", required=True)

    backup_check = backup_sub.add_parser(
        "check", help="Check backups in a JSON file against cadence."
    )
    backup_check.add_argument(
        "--backups", required=True,
        help="JSON file: list of {service, last_backup, cadence_hours, last_restore_test}.",
    )
    backup_check.add_argument("--now", default=None, help="ISO time for ages (testing).")
    backup_check.add_argument(
        "--restore-max-days", type=int, default=30,
        help="Max days since a restore test (default 30).",
    )
    backup_check.set_defaults(func=cmd_backup_check)

    cost = sub.add_parser("cost", help="Attribute spend by service.")
    cost_sub = cost.add_subparsers(dest="cost_command", required=True)

    cost_report = cost_sub.add_parser(
        "report", help="Report spend from a JSON file."
    )
    cost_report.add_argument(
        "--costs", required=True,
        help="JSON file: list of {service, amount, month}.",
    )
    cost_report.add_argument(
        "--budgets", default=None,
        help="JSON file: {service: budget} mapping.",
    )
    cost_report.add_argument("--month", default=None, help="Month for MoM, e.g. 2026-10.")
    cost_report.add_argument("--prev-month", default=None, help="Previous month, e.g. 2026-09.")
    cost_report.add_argument("--top", type=int, default=5, help="Top spenders to show.")
    cost_report.set_defaults(func=cmd_cost_report)

    toil = sub.add_parser("toil", help="Track toil and automation candidates.")
    toil_sub = toil.add_subparsers(dest="toil_command", required=True)

    toil_report = toil_sub.add_parser(
        "report", help="Report toil from a JSON file."
    )
    toil_report.add_argument(
        "--toil", required=True,
        help="JSON file: list of {task, minutes, category, date}.",
    )
    toil_report.add_argument(
        "--capacity-minutes", type=float, default=0.0,
        help="Available team minutes for the toil-share calculation.",
    )
    toil_report.add_argument(
        "--threshold", type=float, default=120.0,
        help="Min minutes for an automation candidate (default 120).",
    )
    toil_report.set_defaults(func=cmd_toil_report)

    deps = sub.add_parser("deps", help="Analyze service dependencies.")
    deps_sub = deps.add_subparsers(dest="deps_command", required=True)

    deps_report = deps_sub.add_parser(
        "report", help="Blast-radius report for a graph."
    )
    deps_report.add_argument(
        "--graph", required=True,
        help="JSON file: {service: [dependencies]}.",
    )
    deps_report.add_argument(
        "--service", default=None,
        help="Focus on one service; omit for the full graph report.",
    )
    deps_report.set_defaults(func=cmd_deps_report)

    monitor = sub.add_parser("monitor", help="Lint alert rules.")
    monitor_sub = monitor.add_subparsers(dest="monitor_command", required=True)

    monitor_lint = monitor_sub.add_parser(
        "lint", help="Lint alert rules from a JSON file."
    )
    monitor_lint.add_argument(
        "--rules", required=True,
        help="JSON file: list of {name, severity, runbook, owner, enabled}.",
    )
    monitor_lint.set_defaults(func=cmd_monitor_lint)

    audit = sub.add_parser("audit", help="Detect config drift.")
    audit_sub = audit.add_subparsers(dest="audit_command", required=True)

    audit_diff = audit_sub.add_parser(
        "diff", help="Diff expected vs actual config JSON files."
    )
    audit_diff.add_argument("--expected", required=True, help="Expected config JSON.")
    audit_diff.add_argument("--actual", required=True, help="Actual config JSON.")
    audit_diff.set_defaults(func=cmd_audit_diff)

    retention = sub.add_parser("retention", help="Check log retention policy.")
    retention_sub = retention.add_subparsers(dest="retention_command", required=True)

    retention_check = retention_sub.add_parser(
        "check", help="Check retention from a JSON file."
    )
    retention_check.add_argument(
        "--retention", required=True,
        help="JSON file: list of {service, log_type, retention_days, required_days}.",
    )
    retention_check.set_defaults(func=cmd_retention_check)

    queue = sub.add_parser("queue", help="Analyze queue backlogs.")
    queue_sub = queue.add_subparsers(dest="queue_command", required=True)

    queue_check = queue_sub.add_parser(
        "check", help="Check queue backlogs from a JSON file."
    )
    queue_check.add_argument(
        "--queues", required=True,
        help="JSON file: list of {queue, depth, oldest_age_minutes, max_depth, max_age_minutes}.",
    )
    queue_check.set_defaults(func=cmd_queue_check)

    rollout = sub.add_parser("rollout", help="Check rollout progress.")
    rollout_sub = rollout.add_subparsers(dest="rollout_command", required=True)

    rollout_check = rollout_sub.add_parser(
        "check", help="Check rollouts from a JSON file."
    )
    rollout_check.add_argument(
        "--rollouts", required=True,
        help="JSON file: list of {name, service, status, started, deadline_minutes, progress_pct}.",
    )
    rollout_check.add_argument("--now", default=None, help="ISO time for ages (testing).")
    rollout_check.set_defaults(func=cmd_rollout_check)

    canary = sub.add_parser("canary", help="Analyze a canary deployment.")
    canary_sub = canary.add_subparsers(dest="canary_command", required=True)

    canary_analyze = canary_sub.add_parser(
        "analyze", help="Compare canary vs baseline and give a verdict."
    )
    canary_analyze.add_argument("--canary-error-rate", type=float, required=True,
                                help="Canary error rate as a fraction, e.g. 0.02.")
    canary_analyze.add_argument("--baseline-error-rate", type=float, required=True,
                                help="Baseline error rate as a fraction.")
    canary_analyze.add_argument("--canary-p99", type=float, required=True,
                                help="Canary p99 latency in ms.")
    canary_analyze.add_argument("--baseline-p99", type=float, required=True,
                                help="Baseline p99 latency in ms.")
    canary_analyze.add_argument("--canary-requests", type=int, required=True,
                                help="Requests observed on the canary.")
    canary_analyze.add_argument("--max-error-delta", type=float, default=0.01,
                                help="Allowed error-rate rise (default 0.01).")
    canary_analyze.add_argument("--max-p99-ratio", type=float, default=1.5,
                                help="Allowed canary/baseline p99 ratio (default 1.5).")
    canary_analyze.add_argument("--min-requests", type=int, default=100,
                                help="Min requests for a decision (default 100).")
    canary_analyze.set_defaults(func=cmd_canary_analyze)

    probe = sub.add_parser("probe", help="Probe endpoints for health.")
    probe_sub = probe.add_subparsers(dest="probe_command", required=True)

    probe_check = probe_sub.add_parser(
        "check", help="Probe one or more URLs."
    )
    probe_check.add_argument("urls", nargs="+", help="URLs to probe.")
    probe_check.add_argument("--expect", type=int, default=200,
                             help="Expected status code (default 200).")
    probe_check.add_argument("--max-latency-ms", type=float, default=1000.0,
                             help="Max latency in ms (default 1000).")
    probe_check.add_argument("--timeout", type=float, default=5.0,
                             help="Request timeout in seconds (default 5).")
    probe_check.set_defaults(func=cmd_probe_check)

    health = sub.add_parser("health", help="Roll up service health checks.")
    health_sub = health.add_subparsers(dest="health_command", required=True)

    health_rollup = health_sub.add_parser(
        "rollup", help="Roll up health checks from a JSON file."
    )
    health_rollup.add_argument(
        "--checks", required=True,
        help="JSON file: list of {service, status, latency_ms}.",
    )
    health_rollup.set_defaults(func=cmd_health_rollup)

    service = sub.add_parser("service", help="Audit the service catalog.")
    service_sub = service.add_subparsers(dest="service_command", required=True)

    service_audit = service_sub.add_parser(
        "audit", help="Audit services from a JSON file."
    )
    service_audit.add_argument(
        "--services", required=True,
        help="JSON file: list of {name, owner, tier, runbook}.",
    )
    service_audit.set_defaults(func=cmd_service_audit)

    dora = sub.add_parser("dora", help="Report DORA metrics.")
    dora_sub = dora.add_subparsers(dest="dora_command", required=True)

    dora_report = dora_sub.add_parser(
        "report", help="DORA metrics from deploy records."
    )
    dora_report.add_argument(
        "--deploys", required=True,
        help="JSON file: list of {service, timestamp, status, lead_time_hours}.",
    )
    dora_report.add_argument("--since", default=None, help="Window start, YYYY-MM-DD.")
    dora_report.add_argument("--until", default=None, help="Window end, YYYY-MM-DD.")
    dora_report.set_defaults(func=cmd_dora_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
