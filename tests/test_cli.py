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
