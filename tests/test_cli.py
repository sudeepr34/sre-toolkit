import json

import pytest

from sre_toolkit.cli import main

SAMPLE_ALERTS = [
    {"name": "HighCPU", "timestamp": "2026-10-10T10:00:00", "state": "firing", "labels": {"instance": "web-1"}},
    {"name": "HighCPU", "timestamp": "2026-10-10T10:01:00", "state": "firing", "labels": {"instance": "web-1"}},
    {"name": "DiskFull", "timestamp": "2026-10-10T10:02:00", "state": "firing", "labels": {"instance": "db-1"}},
]


def _write_alerts(tmp_path):
    path = tmp_path / "alerts.json"
    path.write_text(json.dumps(SAMPLE_ALERTS))
    return str(path)


def test_alerts_command_reports_noise(tmp_path, capsys):
    rc = main(["alerts", _write_alerts(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "total alerts: 3 (2 unique)" in out
    assert "duplicates suppressed: 1" in out
    assert "[2x] HighCPU" in out


def test_alerts_command_flags_flapping(tmp_path, capsys):
    alerts = [
        {"name": "Flap", "timestamp": f"t{i}", "state": s, "labels": {"instance": "x"}}
        for i, s in enumerate(["firing", "resolved", "firing", "resolved"])
    ]
    path = tmp_path / "flap.json"
    path.write_text(json.dumps(alerts))
    rc = main(["alerts", str(path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "flapping:" in out
    assert "[FLAPPING]" in out


def test_runbook_command_prints_checklist(capsys):
    rc = main(["runbook"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# Database primary failover" in out
    assert "- [ ] 1. Confirm primary is unhealthy" in out
    assert "Progress: 0% (0/6)" in out
    assert "next step: Confirm primary is unhealthy" in out


def test_runbook_command_marks_steps_complete(capsys):
    rc = main(["runbook", "--complete", "1,2"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "- [x] 1. Confirm primary is unhealthy" in out
    assert "- [x] 2. Page DBA secondary" in out
    assert "- [ ] 3." in out
    assert "Progress: 33% (2/6)" in out
    assert "next step: Promote replica" in out


def test_handoff_command_prints_template(capsys):
    rc = main(["handoff", "--shift", "2026-10-12", "--outgoing", "priya"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# On-call handoff: 2026-10-12" in out
    assert "- Outgoing: priya" in out
    assert "## Open incidents" in out
    assert "## Pending follow-ups" in out


def test_handoff_command_renders_json_file(tmp_path, capsys):
    payload = {
        "shift": "2026-10-12",
        "outgoing": "priya",
        "incoming": "sudeep",
        "open_incidents": [{"title": "DB latency spike", "severity": "SEV-2"}],
        "follow_ups": [{"task": "rotate the schedule", "due": "Tue"}],
    }
    path = tmp_path / "handoff.json"
    path.write_text(json.dumps(payload))
    rc = main(["handoff", "--file", str(path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# On-call handoff: 2026-10-12" in out
    assert "- Outgoing: priya" in out
    assert "- Incoming: sudeep" in out
    assert "- [SEV-2] DB latency spike (mitigated, owner: on-call)" in out
    assert "- rotate the schedule (owner: on-call, due: Tue)" in out


def test_handoff_cli_flags_override_json_file(tmp_path, capsys):
    payload = {"shift": "2026-10-12", "incoming": "sudeep"}
    path = tmp_path / "handoff.json"
    path.write_text(json.dumps(payload))
    rc = main(["handoff", "--file", str(path), "--incoming", "anil"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "- Incoming: anil" in out
    assert "# On-call handoff: 2026-10-12" in out


def test_slo_command_assesses_burn_rate(capsys):
    rc = main(["slo", "--target", "99.9", "--error-rate", "0.5"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Burn rate: 5.00x" in out
    assert "Severity: **watch**" in out


def test_slo_command_rejects_bad_target(capsys):
    rc = main(["slo", "--target", "100"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "error:" in err


def test_slo_command_reads_json_file(tmp_path, capsys):
    path = tmp_path / "slo.json"
    path.write_text(json.dumps({"slo_target": 0.99, "observed_error_ratio": 0.02}))
    rc = main(["slo", "--file", str(path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Burn rate: 2.00x" in out
    assert "Severity: **watch**" in out


def test_deploy_command_allowed_without_freezes(capsys):
    rc = main(["deploy", "--now", "2026-10-18T12:00"])
    assert rc == 0
    assert "ALLOWED" in capsys.readouterr().out


def test_deploy_command_blocked_in_freeze_window(tmp_path, capsys):
    path = tmp_path / "freezes.json"
    path.write_text(
        json.dumps(
            {
                "freezes": [
                    {
                        "name": "diwali",
                        "start": "2026-10-18T00:00",
                        "end": "2026-10-20T00:00",
                        "reason": "festival blackout",
                    }
                ]
            }
        )
    )
    rc = main(["deploy", "--freezes", str(path), "--now", "2026-10-19T12:00"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "BLOCKED" in out
    assert "diwali" in out


def test_deploy_command_rejects_bad_now(capsys):
    rc = main(["deploy", "--now", "not-a-date"])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_comms_command_prints_template(capsys):
    rc = main(["comms", "--title", "checkout api errors", "--status", "identified"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# checkout api errors" in out
    assert "**identified**" in out
    assert "No updates published yet" in out


def test_comms_command_appends_message(tmp_path, capsys):
    path = tmp_path / "status.json"
    path.write_text(
        json.dumps({"title": "db outage", "status": "investigating"})
    )
    rc = main(
        [
            "comms",
            "--file",
            str(path),
            "--message",
            "Rollback complete, monitoring.",
            "--now",
            "2026-10-19T10:30",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "### 2026-10-19T10:30 — investigating" in out
    assert "Rollback complete, monitoring." in out


def test_comms_command_rejects_bad_status_override(tmp_path, capsys):
    path = tmp_path / "status.json"
    path.write_text(json.dumps({"title": "db outage"}))
    rc = main(["comms", "--file", str(path), "--status", "vibing"])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


ESCALATE_BOOK = {
    "policies": {
        "SEV-1": {
            "name": "sev1-core",
            "levels": [
                {"wait_minutes": 5, "targets": ["primary-oncall"]},
                {"wait_minutes": 0, "targets": ["eng-manager"]},
            ],
        },
        "SEV-2": {"levels": [{"wait_minutes": 30, "targets": ["primary-oncall"]}]},
    },
    "default": "SEV-2",
}


def _write_book(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(ESCALATE_BOOK))
    return str(path)


def test_escalate_command_resolves_current_level(tmp_path, capsys):
    rc = main(
        [
            "escalate",
            _write_book(tmp_path),
            "--severity",
            "SEV-1",
            "--elapsed",
            "12",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Current level: 2 of 2" in out
    assert "Page now: eng-manager" in out


def test_escalate_command_uses_default_policy(tmp_path, capsys):
    rc = main(["escalate", _write_book(tmp_path), "--elapsed", "0"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Current level: 1 of 1" in out


def test_escalate_command_rejects_missing_file(capsys):
    rc = main(["escalate", "/nonexistent/policy.json"])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_oncall_command_shows_who_is_on(tmp_path, capsys):
    path = tmp_path / "rota.json"
    path.write_text(
        json.dumps(
            {
                "name": "backend",
                "members": ["priya", "sudeep"],
                "start_date": "2026-10-05",
                "shift_days": 7,
            }
        )
    )
    rc = main(["oncall", str(path), "--date", "2026-10-14"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "On call now: **sudeep**" in out
    assert "2026-10-19: priya" in out


def test_oncall_command_rejects_bad_date(tmp_path, capsys):
    path = tmp_path / "rota.json"
    path.write_text(json.dumps({"members": ["solo"], "start_date": "2026-10-05"}))
    rc = main(["oncall", str(path), "--date", "not-a-date"])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_review_command_rolls_up_postmortems(tmp_path, capsys):
    incident = {
        "title": "db outage",
        "severity": "SEV-1",
        "timeline": [
            {"timestamp": "2026-10-20T09:00", "title": "a", "milestone": "detected"},
            {"timestamp": "2026-10-20T09:30", "title": "b", "milestone": "mitigated"},
        ],
        "contributing_factors": ["bad deploy"],
        "action_items": [{"task": "add canary", "owner": "sudeep"}],
    }
    path = tmp_path / "incident.json"
    path.write_text(json.dumps(incident))
    rc = main(["review", "--week", "2026-W42", str(path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# Ops review: 2026-W42" in out
    assert "Incidents reviewed: 1" in out
    assert "Mean time to mitigate: 30m" in out
    assert "add canary" in out


def test_review_command_rejects_zero_files(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["review", "--week", "2026-W42"])
    assert exc_info.value.code == 2


def _incident_args(tmp_path, *rest):
    return ["incident", "--state", str(tmp_path / "incidents.json"), *rest]


def test_incident_start_and_status(tmp_path, capsys):
    rc = main(
        _incident_args(tmp_path, "start", "--title", "db outage", "--severity", "SEV-1",
           "--started", "2026-10-23T09:00")
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "# Incident INC-0001: db outage" in out

    rc = main(
        _incident_args(tmp_path, "status", "INC-0001", "--now", "2026-10-23T09:45")
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Elapsed: 45m" in out


def test_incident_note_list_resolve(tmp_path, capsys):
    main(_incident_args(tmp_path, "start", "--title", "x"))
    rc = main(
        _incident_args(tmp_path, "note", "INC-0001", "--message", "looking",
           "--at", "2026-10-23T09:10")
    )
    assert rc == 0
    assert "note added to INC-0001" in capsys.readouterr().out

    rc = main(_incident_args(tmp_path, "list"))
    assert rc == 0
    assert "INC-0001 [open] x (SEV-3)" in capsys.readouterr().out

    rc = main(
        _incident_args(tmp_path, "resolve", "INC-0001", "--at", "2026-10-23T10:00")
    )
    assert rc == 0
    assert "**resolved**" in capsys.readouterr().out

    rc = main(_incident_args(tmp_path, "list"))
    assert rc == 0
    assert "no open incidents" in capsys.readouterr().out


def test_incident_set_status(tmp_path, capsys):
    main(_incident_args(tmp_path, "start", "--title", "x"))
    rc = main(
        _incident_args(tmp_path, "set-status", "INC-0001", "--status", "acknowledged")
    )
    assert rc == 0
    assert "**acknowledged**" in capsys.readouterr().out


def test_incident_unknown_id_errors(tmp_path, capsys):
    rc = main(_incident_args(tmp_path, "status", "INC-9999"))
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_capacity_forecast(tmp_path, capsys):
    rc = main([
        "capacity", "forecast",
        "--current-load", "600", "--capacity", "1000",
        "--growth", "0.10", "--periods", "3",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "| 2 | 726.0 rps | 72.6% | breach |" in out
    assert "crosses target at period 2" in out


def test_capacity_invalid_target_errors(tmp_path, capsys):
    rc = main([
        "capacity", "forecast",
        "--current-load", "600", "--capacity", "1000",
        "--growth", "0.10", "--target", "1.5",
    ])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_drill_list(tmp_path, capsys):
    rc = main(["drill", "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "db-failover - Primary database failover" in out
    assert "bad-deploy - Bad deploy rollback" in out


def test_drill_show(tmp_path, capsys):
    rc = main(["drill", "show", "cache-outage"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# Drill: Cache layer outage" in out
    assert "## Success criteria" in out


def test_drill_run(tmp_path, capsys):
    rc = main(["drill", "run", "disk-full", "--date", "2026-10-25"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# Drill run: Disk pressure on a node" in out
    assert "Date: 2026-10-25" in out
    assert "- [ ] [on-call]" in out


def test_drill_unknown_id_errors(tmp_path, capsys):
    rc = main(["drill", "show", "meteor-strike"])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_backup_check(tmp_path, capsys):
    import json as _json
    data = [
        {"service": "api-db", "last_backup": "2026-10-26T10:00",
         "cadence_hours": 24, "last_restore_test": "2026-10-20"},
        {"service": "cache", "last_backup": "", "cadence_hours": 24,
         "last_restore_test": ""},
    ]
    path = tmp_path / "backups.json"
    path.write_text(_json.dumps(data))
    rc = main([
        "backup", "check", "--backups", str(path), "--now", "2026-10-26T12:00",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "| api-db | ok |" in out
    assert "| cache | never |" in out
    assert "## Needs attention" in out


def test_backup_check_missing_file_errors(tmp_path, capsys):
    rc = main(["backup", "check", "--backups", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_cost_report(tmp_path, capsys):
    import json as _json
    costs = tmp_path / "costs.json"
    costs.write_text(_json.dumps([
        {"service": "api", "amount": 400, "month": "2026-10"},
        {"service": "db", "amount": 300, "month": "2026-10"},
        {"service": "api", "amount": 100, "month": "2026-09"},
    ]))
    budgets = tmp_path / "budgets.json"
    budgets.write_text(_json.dumps({"api": 450}))
    rc = main([
        "cost", "report", "--costs", str(costs), "--budgets", str(budgets),
        "--month", "2026-10", "--prev-month", "2026-09",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Total spend: 800.00" in out
    assert "| api | 500.00 | 62.5% |" in out
    assert "## Over budget" in out


def test_cost_report_missing_file_errors(tmp_path, capsys):
    rc = main(["cost", "report", "--costs", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_toil_report(tmp_path, capsys):
    import json as _json
    path = tmp_path / "toil.json"
    path.write_text(_json.dumps([
        {"task": "restart pods", "minutes": 180, "category": "manual"},
        {"task": "rotate certs", "minutes": 300, "category": "automatable"},
    ]))
    rc = main([
        "toil", "report", "--toil", str(path), "--capacity-minutes", "960",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Total toil: 480 minutes (8.0 hours)" in out
    assert "Share of capacity: 50.0%" in out
    assert "- rotate certs: 300 minutes" in out


def test_toil_report_missing_file_errors(tmp_path, capsys):
    rc = main(["toil", "report", "--toil", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_deps_report_service(tmp_path, capsys):
    import json as _json
    path = tmp_path / "graph.json"
    path.write_text(_json.dumps({
        "api": ["db", "cache"], "web": ["api"], "db": [], "cache": ["db"],
    }))
    rc = main(["deps", "report", "--graph", str(path), "--service", "db"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# Dependency report: db" in out
    assert "## Blast radius (3 services)" in out


def test_deps_report_full(tmp_path, capsys):
    import json as _json
    path = tmp_path / "graph.json"
    path.write_text(_json.dumps({"api": ["db"], "db": []}))
    rc = main(["deps", "report", "--graph", str(path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "| db | 0 | 1 | 1 |" in out
    assert "No dependency cycles." in out


def test_deps_report_unknown_service_errors(tmp_path, capsys):
    import json as _json
    path = tmp_path / "graph.json"
    path.write_text(_json.dumps({"api": ["db"], "db": []}))
    rc = main(["deps", "report", "--graph", str(path), "--service", "nope"])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_deps_report_missing_file_errors(tmp_path, capsys):
    rc = main(["deps", "report", "--graph", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_monitor_lint_clean(tmp_path, capsys):
    import json as _json
    path = tmp_path / "rules.json"
    path.write_text(_json.dumps([
        {"name": "HighLatency", "severity": "critical",
         "runbook": "https://runbooks/latency", "owner": "sre"},
    ]))
    rc = main(["monitor", "lint", "--rules", str(path)])
    assert rc == 0
    assert "All rules clean" in capsys.readouterr().out


def test_monitor_lint_issues_exit_1(tmp_path, capsys):
    import json as _json
    path = tmp_path / "rules.json"
    path.write_text(_json.dumps([
        {"name": "HighLatency", "severity": "", "runbook": "", "owner": "sre"},
    ]))
    rc = main(["monitor", "lint", "--rules", str(path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Issues found: 2" in out
    assert "| HighLatency | severity | no severity set |" in out


def test_monitor_lint_missing_file_errors(tmp_path, capsys):
    rc = main(["monitor", "lint", "--rules", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_audit_diff_clean(tmp_path, capsys):
    import json as _json
    expected = tmp_path / "expected.json"
    actual = tmp_path / "actual.json"
    expected.write_text(_json.dumps({"replicas": 3}))
    actual.write_text(_json.dumps({"replicas": 3}))
    rc = main(["audit", "diff", "--expected", str(expected), "--actual", str(actual)])
    assert rc == 0
    assert "No drift" in capsys.readouterr().out


def test_audit_diff_drift_exit_1(tmp_path, capsys):
    import json as _json
    expected = tmp_path / "expected.json"
    actual = tmp_path / "actual.json"
    expected.write_text(_json.dumps({"replicas": 3, "db": {"pool": 10}}))
    actual.write_text(_json.dumps({"replicas": 2, "db": {"pool": 10}}))
    rc = main(["audit", "diff", "--expected", str(expected), "--actual", str(actual)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Drifts found: 1" in out
    assert "| replicas | changed | 3 | 2 |" in out


def test_audit_diff_missing_file_errors(tmp_path, capsys):
    rc = main(["audit", "diff", "--expected", str(tmp_path / "nope.json"),
               "--actual", str(tmp_path / "nope2.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_retention_check_clean(tmp_path, capsys):
    import json as _json
    path = tmp_path / "retention.json"
    path.write_text(_json.dumps([
        {"service": "api", "log_type": "access",
         "retention_days": 90, "required_days": 30},
    ]))
    rc = main(["retention", "check", "--retention", str(path)])
    assert rc == 0
    assert "All retention meets policy." in capsys.readouterr().out


def test_retention_check_gaps_exit_1(tmp_path, capsys):
    import json as _json
    path = tmp_path / "retention.json"
    path.write_text(_json.dumps([
        {"service": "db", "log_type": "access",
         "retention_days": 7, "required_days": 30},
    ]))
    rc = main(["retention", "check", "--retention", str(path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "| db/access | shortfall |" in out
    assert "## Gaps" in out


def test_retention_check_missing_file_errors(tmp_path, capsys):
    rc = main(["retention", "check", "--retention", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_queue_check_clean(tmp_path, capsys):
    import json as _json
    path = tmp_path / "queues.json"
    path.write_text(_json.dumps([
        {"queue": "jobs", "depth": 100, "oldest_age_minutes": 10,
         "max_depth": 1000, "max_age_minutes": 60},
    ]))
    rc = main(["queue", "check", "--queues", str(path)])
    assert rc == 0
    assert "All queues within thresholds." in capsys.readouterr().out


def test_queue_check_breach_exit_1(tmp_path, capsys):
    import json as _json
    path = tmp_path / "queues.json"
    path.write_text(_json.dumps([
        {"queue": "events", "depth": 2000, "oldest_age_minutes": 90,
         "max_depth": 1000, "max_age_minutes": 60},
    ]))
    rc = main(["queue", "check", "--queues", str(path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "| events | breach |" in out
    assert "## Breaches" in out


def test_queue_check_missing_file_errors(tmp_path, capsys):
    rc = main(["queue", "check", "--queues", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_rollout_check_clean(tmp_path, capsys):
    import json as _json
    path = tmp_path / "rollouts.json"
    path.write_text(_json.dumps([
        {"name": "api-v2", "service": "api", "status": "complete",
         "started": "2026-11-05T11:00", "deadline_minutes": 30, "progress_pct": 100},
    ]))
    rc = main(["rollout", "check", "--rollouts", str(path)])
    assert rc == 0
    assert "All rollouts healthy." in capsys.readouterr().out


def test_rollout_check_stuck_exit_1(tmp_path, capsys):
    import json as _json
    path = tmp_path / "rollouts.json"
    path.write_text(_json.dumps([
        {"name": "api-v2", "service": "api", "status": "progressing",
         "started": "2026-11-05T11:00", "deadline_minutes": 30, "progress_pct": 50},
    ]))
    rc = main(["rollout", "check", "--rollouts", str(path),
               "--now", "2026-11-05T12:00"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "| api-v2 | api | stuck |" in out
    assert "## Needs attention" in out


def test_rollout_check_missing_file_errors(tmp_path, capsys):
    rc = main(["rollout", "check", "--rollouts", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def _canary_args(**overrides):
    args = {
        "--canary-error-rate": "0.011", "--baseline-error-rate": "0.010",
        "--canary-p99": "220", "--baseline-p99": "200",
        "--canary-requests": "500",
    }
    args.update(overrides)
    flat = []
    for key, value in args.items():
        flat.extend([key, value])
    return ["canary", "analyze", *flat]


def test_canary_analyze_promote(tmp_path, capsys):
    rc = main(_canary_args())
    assert rc == 0
    assert "## Verdict: PROMOTE" in capsys.readouterr().out


def test_canary_analyze_rollback_exit_1(tmp_path, capsys):
    rc = main(_canary_args(**{"--canary-error-rate": "0.03"}))
    assert rc == 1
    assert "## Verdict: ROLLBACK" in capsys.readouterr().out


def test_canary_analyze_hold_exit_1(tmp_path, capsys):
    rc = main(_canary_args(**{"--canary-requests": "50"}))
    assert rc == 1
    assert "## Verdict: HOLD" in capsys.readouterr().out


def test_probe_check_local_server(tmp_path, capsys):
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    try:
        rc = main(["probe", "check", url])
    finally:
        httpd.shutdown()
    assert rc == 0
    assert "All endpoints healthy." in capsys.readouterr().out


def test_probe_check_unreachable_exit_1(tmp_path, capsys):
    rc = main(["probe", "check", "http://127.0.0.1:1/", "--timeout", "1"])
    assert rc == 1
    assert "unreachable" in capsys.readouterr().out


def test_health_rollup_all_up(tmp_path, capsys):
    import json as _json
    path = tmp_path / "checks.json"
    path.write_text(_json.dumps([
        {"service": "api", "status": "up", "latency_ms": 120},
    ]))
    rc = main(["health", "rollup", "--checks", str(path)])
    assert rc == 0
    assert "All services up." in capsys.readouterr().out


def test_health_rollup_down_exit_1(tmp_path, capsys):
    import json as _json
    path = tmp_path / "checks.json"
    path.write_text(_json.dumps([
        {"service": "api", "status": "up", "latency_ms": 120},
        {"service": "cache", "status": "down"},
    ]))
    rc = main(["health", "rollup", "--checks", str(path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Overall: **down**" in out
    assert "## Needs attention" in out


def test_health_rollup_missing_file_errors(tmp_path, capsys):
    rc = main(["health", "rollup", "--checks", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_service_audit_clean(tmp_path, capsys):
    import json as _json
    path = tmp_path / "services.json"
    path.write_text(_json.dumps([
        {"name": "api", "owner": "sre", "tier": "critical",
         "runbook": "https://runbooks/api"},
    ]))
    rc = main(["service", "audit", "--services", str(path)])
    assert rc == 0
    assert "Catalog clean" in capsys.readouterr().out


def test_service_audit_issues_exit_1(tmp_path, capsys):
    import json as _json
    path = tmp_path / "services.json"
    path.write_text(_json.dumps([
        {"name": "api", "owner": "", "tier": "critical", "runbook": ""},
    ]))
    rc = main(["service", "audit", "--services", str(path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Issues found: 2" in out
    assert "| api | owner | no owner team |" in out


def test_service_audit_missing_file_errors(tmp_path, capsys):
    rc = main(["service", "audit", "--services", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_dora_report(tmp_path, capsys):
    import json as _json
    path = tmp_path / "deploys.json"
    path.write_text(_json.dumps([
        {"service": "api", "timestamp": "2026-10-10", "status": "success", "lead_time_hours": 4},
        {"service": "api", "timestamp": "2026-10-15", "status": "failed", "lead_time_hours": 6},
        {"service": "web", "timestamp": "2026-09-01", "status": "success"},
    ]))
    rc = main(["dora", "report", "--deploys", str(path),
               "--since", "2026-10-01", "--until", "2026-10-31"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Deploys: 2" in out
    assert "Change failure rate: 50.0%" in out
    assert "| api | 2 | 1 |" in out


def test_dora_report_bad_date_errors(tmp_path, capsys):
    import json as _json
    path = tmp_path / "deploys.json"
    path.write_text(_json.dumps([]))
    rc = main(["dora", "report", "--deploys", str(path), "--since", "not-a-date"])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_dora_report_missing_file_errors(tmp_path, capsys):
    rc = main(["dora", "report", "--deploys", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_latency_analyze_within_threshold(tmp_path, capsys):
    import json as _json
    path = tmp_path / "samples.json"
    path.write_text(_json.dumps([10, 20, 30, 40, 50]))
    rc = main(["latency", "analyze", "--samples", str(path),
               "--p95-threshold", "500"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Samples: 5" in out
    assert "| p95 | 50.0 |" in out
    assert "within threshold" in out


def test_latency_analyze_breach_exit_1(tmp_path, capsys):
    import json as _json
    path = tmp_path / "samples.json"
    path.write_text(_json.dumps([10, 20, 30, 40, 1000]))
    rc = main(["latency", "analyze", "--samples", str(path),
               "--p95-threshold", "500"])
    assert rc == 1
    assert "BREACH" in capsys.readouterr().out


def test_latency_analyze_missing_file_errors(tmp_path, capsys):
    rc = main(["latency", "analyze", "--samples", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_cert_check_ok_exit_0(tmp_path, capsys):
    import json as _json
    path = tmp_path / "certs.json"
    path.write_text(_json.dumps([
        {"host": "a.example.com", "expires": "2027-01-01"},
    ]))
    rc = main(["cert", "check", "--certs", str(path), "--today", "2026-11-06"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Certificates checked: 1" in out
    assert "- OK: 1" in out


def test_cert_check_critical_exit_1(tmp_path, capsys):
    import json as _json
    path = tmp_path / "certs.json"
    path.write_text(_json.dumps([
        {"host": "a.example.com", "expires": "2026-11-10"},
        {"host": "b.example.com", "expires": "2026-11-25"},
    ]))
    rc = main(["cert", "check", "--certs", str(path), "--today", "2026-11-06"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "- Critical: 1" in out
    assert "- Warn: 1" in out


def test_cert_check_missing_file_errors(tmp_path, capsys):
    rc = main(["cert", "check", "--certs", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def _trace_json():
    import json as _json
    return _json.dumps([
        {"trace_id": "t1", "span_id": "r", "parent_id": "",
         "service": "edge", "operation": "handle", "start_ms": 0, "duration_ms": 100},
        {"trace_id": "t1", "span_id": "a", "parent_id": "r",
         "service": "api", "operation": "process", "start_ms": 10, "duration_ms": 80},
        {"trace_id": "t1", "span_id": "c", "parent_id": "a",
         "service": "cache", "operation": "get", "start_ms": 20, "duration_ms": 10,
         "status": "error"},
    ])


def test_trace_analyze_error_exit_1(tmp_path, capsys):
    path = tmp_path / "spans.json"
    path.write_text(_trace_json())
    rc = main(["trace", "analyze", "--spans", str(path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Spans: 3" in out
    assert "Critical path: 190.0 ms" in out
    assert "cache::get (c)" in out


def test_trace_analyze_trace_filter(tmp_path, capsys):
    import json as _json
    path = tmp_path / "spans.json"
    data = _json.loads(_trace_json())
    data.append({"trace_id": "t2", "span_id": "x", "parent_id": "",
                 "service": "other", "operation": "run",
                 "start_ms": 0, "duration_ms": 5})
    path.write_text(_json.dumps(data))
    rc = main(["trace", "analyze", "--spans", str(path), "--trace-id", "t2"])
    assert rc == 0
    assert "Spans: 1" in capsys.readouterr().out


def test_trace_analyze_no_spans_errors(tmp_path, capsys):
    import json as _json
    path = tmp_path / "spans.json"
    path.write_text(_json.dumps([]))
    rc = main(["trace", "analyze", "--spans", str(path)])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_flags_audit_clean(tmp_path, capsys):
    import json as _json
    path = tmp_path / "flags.json"
    path.write_text(_json.dumps([
        {"name": "new-checkout", "enabled": True, "owner": "sre",
         "last_used": "2026-11-05", "created": "2026-01-01"},
    ]))
    rc = main(["flags", "audit", "--flags", str(path), "--today", "2026-11-06"])
    assert rc == 0
    assert "Flags clean" in capsys.readouterr().out


def test_flags_audit_issues_exit_1(tmp_path, capsys):
    import json as _json
    path = tmp_path / "flags.json"
    path.write_text(_json.dumps([
        {"name": "old", "enabled": True, "owner": "",
         "last_used": "2026-01-01", "created": "2026-01-01"},
    ]))
    rc = main(["flags", "audit", "--flags", str(path), "--today", "2026-11-06"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Issues found: 2" in out
    assert "| old | owner | no owner team |" in out


def test_flags_audit_missing_file_errors(tmp_path, capsys):
    rc = main(["flags", "audit", "--flags", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_dns_check_localhost_ok(capsys):
    rc = main(["dns", "check", "localhost"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Hosts checked: 1" in out
    assert "| localhost | 127.0.0.1 | ok |" in out


def test_dns_check_failure_exit_1(capsys):
    rc = main(["dns", "check", "localhost", "not a host"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "- Failed: 1" in out
    assert "failed:" in out


def test_sla_check_compliant_exit_0(tmp_path, capsys):
    import json as _json
    path = tmp_path / "sla.json"
    path.write_text(_json.dumps([
        {"service": "api", "uptime_pct": 99.95, "target_pct": 99.9},
    ]))
    rc = main(["sla", "check", "--sla", str(path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Services checked: 1" in out
    assert "- Breached: 0" in out
    assert "| api | 99.950% | 99.900% | 21.6 | compliant |" in out


def test_sla_check_breach_exit_1(tmp_path, capsys):
    import json as _json
    path = tmp_path / "sla.json"
    path.write_text(_json.dumps([
        {"service": "db", "uptime_pct": 99.5, "target_pct": 99.9},
    ]))
    rc = main(["sla", "check", "--sla", str(path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "- Breached: 1" in out
    assert "BREACHED" in out


def test_sla_check_missing_file_errors(tmp_path, capsys):
    rc = main(["sla", "check", "--sla", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_secrets_audit_ok_exit_0(tmp_path, capsys):
    import json as _json
    path = tmp_path / "secrets.json"
    path.write_text(_json.dumps([
        {"name": "db-password", "last_rotated": "2026-10-01",
         "rotation_days": 90, "owner": "sre"},
    ]))
    rc = main(["secrets", "audit", "--secrets", str(path), "--today", "2026-11-07"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Secrets checked: 1" in out
    assert "- OK: 1" in out
    assert "- Issues found: 0" in out


def test_secrets_audit_overdue_exit_1(tmp_path, capsys):
    import json as _json
    path = tmp_path / "secrets.json"
    path.write_text(_json.dumps([
        {"name": "api-key", "last_rotated": "2026-07-01",
         "rotation_days": 90, "owner": "sre"},
    ]))
    rc = main(["secrets", "audit", "--secrets", str(path), "--today", "2026-11-07"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "- Overdue: 1" in out
    assert "| api-key | overdue | overdue by 39 days |" in out


def test_secrets_audit_missing_file_errors(tmp_path, capsys):
    rc = main(["secrets", "audit", "--secrets", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_rollback_check_ready_exit_0(tmp_path, capsys):
    import json as _json
    path = tmp_path / "deploys.json"
    path.write_text(_json.dumps([
        {"service": "api", "version": "v2.1.0", "previous_version": "v2.0.9",
         "rollback_runbook": "https://runbooks/rollback-api",
         "rollback_tested": True},
    ]))
    rc = main(["rollback", "check", "--deploys", str(path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Deploys checked: 1" in out
    assert "All deploys are rollback-ready" in out


def test_rollback_check_issues_exit_1(tmp_path, capsys):
    import json as _json
    path = tmp_path / "deploys.json"
    path.write_text(_json.dumps([
        {"service": "api", "version": "v2.1.0", "previous_version": "",
         "rollback_runbook": "", "rollback_tested": False},
    ]))
    rc = main(["rollback", "check", "--deploys", str(path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Issues found: 3" in out
    assert "| api | v2.1.0 | untested | rollback never tested |" in out


def test_rollback_check_missing_file_errors(tmp_path, capsys):
    rc = main(["rollback", "check", "--deploys", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_events_correlate_burst_exit_1(tmp_path, capsys):
    import json as _json
    path = tmp_path / "events.json"
    path.write_text(_json.dumps([
        {"service": "api", "timestamp": f"2026-11-10T10:{m:02d}:00",
         "severity": "error", "message": "fail"}
        for m in range(5)
    ] + [
        {"service": "db", "timestamp": "2026-11-10T10:05:00",
         "severity": "error", "message": "fail"},
    ]))
    rc = main(["events", "correlate", "--events", str(path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "- Bursts found: 1" in out
    assert "- Correlated windows: 1" in out
    assert "| api | 2026-11-10T10:00:00 | 5 |" in out


def test_events_correlate_clean_exit_0(tmp_path, capsys):
    import json as _json
    path = tmp_path / "events.json"
    path.write_text(_json.dumps([
        {"service": "api", "timestamp": "2026-11-10T10:00:00"},
        {"service": "api", "timestamp": "2026-11-10T11:00:00"},
    ]))
    rc = main(["events", "correlate", "--events", str(path)])
    assert rc == 0
    assert "No bursts or correlated windows found." in capsys.readouterr().out


def test_events_correlate_missing_file_errors(tmp_path, capsys):
    rc = main(["events", "correlate", "--events", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_change_check_clean_exit_0(tmp_path, capsys):
    import json as _json
    path = tmp_path / "changes.json"
    path.write_text(_json.dumps([
        {"id": "c1", "service": "api",
         "start": "2026-11-12T02:00:00", "end": "2026-11-12T04:00:00"},
        {"id": "c2", "service": "db",
         "start": "2026-11-12T03:00:00", "end": "2026-11-12T05:00:00"},
    ]))
    rc = main(["change", "check", "--changes", str(path)])
    assert rc == 0
    assert "No collisions" in capsys.readouterr().out


def test_change_check_collision_exit_1(tmp_path, capsys):
    import json as _json
    path = tmp_path / "changes.json"
    path.write_text(_json.dumps([
        {"id": "c1", "service": "api",
         "start": "2026-11-12T02:00:00", "end": "2026-11-12T04:00:00"},
        {"id": "c2", "service": "api",
         "start": "2026-11-12T03:00:00", "end": "2026-11-12T05:00:00"},
    ]))
    rc = main(["change", "check", "--changes", str(path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Collisions found: 1" in out
    assert "| api | c1 | c2 |" in out


def test_change_check_missing_file_errors(tmp_path, capsys):
    rc = main(["change", "check", "--changes", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_vuln_triage_ok_exit_0(tmp_path, capsys):
    import json as _json
    path = tmp_path / "findings.json"
    path.write_text(_json.dumps([
        {"id": "CVE-2026-0001", "severity": "high", "service": "api",
         "discovered": "2026-10-20"},
    ]))
    rc = main(["vuln", "triage", "--findings", str(path), "--today", "2026-11-11"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Findings checked: 1" in out
    assert "- Overdue: 0" in out


def test_vuln_triage_overdue_exit_1(tmp_path, capsys):
    import json as _json
    path = tmp_path / "findings.json"
    path.write_text(_json.dumps([
        {"id": "CVE-2026-0001", "severity": "critical", "service": "api",
         "discovered": "2026-10-20"},
    ]))
    rc = main(["vuln", "triage", "--findings", str(path), "--today", "2026-11-11"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "- Overdue: 1" in out
    assert "| CVE-2026-0001 | critical | api | 22 | 7 | overdue |" in out


def test_vuln_triage_missing_file_errors(tmp_path, capsys):
    rc = main(["vuln", "triage", "--findings", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_schedule_coverage_full_exit_0(tmp_path, capsys):
    import json as _json
    path = tmp_path / "shifts.json"
    path.write_text(_json.dumps([
        {"person": "a", "start": "2026-11-01", "end": "2026-11-15"},
        {"person": "b", "start": "2026-11-16", "end": "2026-11-30"},
    ]))
    rc = main(["schedule", "coverage", "--shifts", str(path),
               "--since", "2026-11-01", "--until", "2026-11-30"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Coverage: 100.0%" in out
    assert "Full coverage" in out


def test_schedule_coverage_gap_exit_1(tmp_path, capsys):
    import json as _json
    path = tmp_path / "shifts.json"
    path.write_text(_json.dumps([
        {"person": "a", "start": "2026-11-01", "end": "2026-11-10"},
        {"person": "b", "start": "2026-11-15", "end": "2026-11-30"},
    ]))
    rc = main(["schedule", "coverage", "--shifts", str(path),
               "--since", "2026-11-01", "--until", "2026-11-30"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Gaps found: 1" in out
    assert "| 2026-11-11 | 2026-11-14 | 4 |" in out


def test_schedule_coverage_missing_file_errors(tmp_path, capsys):
    rc = main(["schedule", "coverage", "--shifts", str(tmp_path / "nope.json"),
               "--since", "2026-11-01", "--until", "2026-11-30"])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def _freezes_json():
    import json as _json
    return _json.dumps([
        {"name": "black-friday", "start": "2026-11-27T00:00:00",
         "end": "2026-11-30T23:59:59", "reason": "peak traffic"},
    ])


def test_maintenance_check_clear_exit_0(tmp_path, capsys):
    path = tmp_path / "freezes.json"
    path.write_text(_freezes_json())
    rc = main(["maintenance", "check", "--service", "api",
               "--start", "2026-11-12T02:00:00", "--end", "2026-11-12T04:00:00",
               "--freezes", str(path)])
    assert rc == 0
    assert "Clear: the window does not overlap any freeze." in capsys.readouterr().out


def test_maintenance_check_conflict_exit_1(tmp_path, capsys):
    path = tmp_path / "freezes.json"
    path.write_text(_freezes_json())
    rc = main(["maintenance", "check", "--service", "api",
               "--start", "2026-11-28T02:00:00", "--end", "2026-11-28T04:00:00",
               "--freezes", str(path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Conflicts found: 1" in out
    assert "| black-friday | peak traffic |" in out


def test_maintenance_check_missing_file_errors(tmp_path, capsys):
    rc = main(["maintenance", "check", "--service", "api",
               "--start", "2026-11-12T02:00:00", "--end", "2026-11-12T04:00:00",
               "--freezes", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_pods_check_ok_exit_0(tmp_path, capsys):
    import json as _json
    path = tmp_path / "pods.json"
    path.write_text(_json.dumps([
        {"name": "api-abc", "namespace": "prod", "restarts": 0, "age_hours": 48},
        {"name": "api-def", "namespace": "prod", "restarts": 2, "age_hours": 48},
    ]))
    rc = main(["pods", "check", "--pods", str(path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Pods checked: 2" in out
    assert "- Critical: 0" in out


def test_pods_check_critical_exit_1(tmp_path, capsys):
    import json as _json
    path = tmp_path / "pods.json"
    path.write_text(_json.dumps([
        {"name": "api-abc", "namespace": "prod", "restarts": 12, "age_hours": 24},
    ]))
    rc = main(["pods", "check", "--pods", str(path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "- Critical: 1" in out
    assert "| api-abc | prod | 12 | 12.0 | critical |" in out


def test_pods_check_missing_file_errors(tmp_path, capsys):
    rc = main(["pods", "check", "--pods", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_inventory_audit_clean_exit_0(tmp_path, capsys):
    import json as _json
    path = tmp_path / "hosts.json"
    path.write_text(_json.dumps([
        {"name": "web-01", "owner": "sre", "environment": "prod",
         "patched": True, "last_patched": "2026-11-01"},
    ]))
    rc = main(["inventory", "audit", "--hosts", str(path), "--today", "2026-11-11"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Hosts checked: 1" in out
    assert "Hosts with issues: 0" in out


def test_inventory_audit_issues_exit_1(tmp_path, capsys):
    import json as _json
    path = tmp_path / "hosts.json"
    path.write_text(_json.dumps([
        {"name": "db-01", "owner": "", "environment": "prod",
         "patched": False, "last_patched": ""},
    ]))
    rc = main(["inventory", "audit", "--hosts", str(path), "--today", "2026-11-11"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Hosts with issues: 1" in out
    assert "| db-01 | prod | — | missing owner, unpatched |" in out


def test_inventory_audit_missing_file_errors(tmp_path, capsys):
    rc = main(["inventory", "audit", "--hosts", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_releases_cadence_fresh_exit_0(tmp_path, capsys):
    import json as _json
    path = tmp_path / "releases.json"
    path.write_text(_json.dumps([
        {"version": "v1.4.2", "service": "api", "date": "2026-11-10"},
    ]))
    rc = main(["releases", "cadence", "--releases", str(path), "--today", "2026-11-12"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Services checked: 1" in out
    assert "Stale services: 0" in out


def test_releases_cadence_stale_exit_1(tmp_path, capsys):
    import json as _json
    path = tmp_path / "releases.json"
    path.write_text(_json.dumps([
        {"version": "v1.0.0", "service": "api", "date": "2026-09-01"},
    ]))
    rc = main(["releases", "cadence", "--releases", str(path), "--today", "2026-11-12"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Stale services: 1" in out
    assert "| api | v1.0.0 | 2026-09-01 | 72 | yes |" in out


def test_releases_cadence_missing_file_errors(tmp_path, capsys):
    rc = main(["releases", "cadence", "--releases", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err
