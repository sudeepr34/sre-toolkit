import json

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
