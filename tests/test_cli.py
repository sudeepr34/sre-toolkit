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
