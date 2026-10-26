from datetime import datetime

from sre_toolkit.backup import (
    BackupRecord,
    check_backups,
    records_from_json,
    to_markdown,
)

NOW = datetime.fromisoformat("2026-10-26T12:00")


def _record(**kwargs) -> BackupRecord:
    defaults = dict(
        service="api-db",
        last_backup="2026-10-26T10:00",
        cadence_hours=24,
        last_restore_test="2026-10-20",
    )
    defaults.update(kwargs)
    return BackupRecord(**defaults)


def test_ok_when_fresh_and_restore_tested():
    results = check_backups([_record()], now=NOW)
    assert results[0].status == "ok"
    assert "2.0h ago" in results[0].detail


def test_stale_when_past_cadence():
    record = _record(last_backup="2026-10-25T10:00", cadence_hours=24)
    results = check_backups([record], now=NOW)
    assert results[0].status == "stale"
    assert "26.0h ago" in results[0].detail


def test_exactly_at_cadence_is_ok():
    record = _record(last_backup="2026-10-25T12:00", cadence_hours=24)
    results = check_backups([record], now=NOW)
    assert results[0].status == "ok"


def test_never_when_no_backup_recorded():
    record = _record(last_backup="")
    results = check_backups([record], now=NOW)
    assert results[0].status == "never"
    assert "no backup recorded" in results[0].detail


def test_restore_stale_when_never_tested():
    record = _record(last_restore_test="")
    results = check_backups([record], now=NOW)
    assert results[0].status == "restore-stale"
    assert "never tested" in results[0].detail


def test_restore_stale_when_test_too_old():
    record = _record(last_restore_test="2026-09-01")
    results = check_backups([record], now=NOW)
    assert results[0].status == "restore-stale"
    assert "56d ago" in results[0].detail


def test_stale_beats_restore_stale():
    record = _record(last_backup="2026-10-20T12:00", last_restore_test="")
    results = check_backups([record], now=NOW)
    assert results[0].status == "stale"


def test_restore_max_days_is_configurable():
    record = _record(last_restore_test="2026-09-27")  # 29.5 days ago
    assert check_backups([record], now=NOW, restore_max_days=30)[0].status == "ok"
    assert check_backups([record], now=NOW, restore_max_days=7)[0].status == "restore-stale"


def test_markdown_lists_problems():
    results = check_backups(
        [_record(), _record(service="cache", last_backup="")], now=NOW
    )
    md = to_markdown(results)
    assert "# Backup verification" in md
    assert "| api-db | ok |" in md
    assert "| cache | never |" in md
    assert "## Needs attention" in md
    assert "- cache: no backup recorded" in md


def test_markdown_all_ok_message():
    md = to_markdown(check_backups([_record()], now=NOW))
    assert "All backups fresh and restore tests current." in md


def test_records_from_json_defaults():
    records = records_from_json([{"service": "x"}])
    assert records[0].cadence_hours == 24
    assert records[0].last_backup == ""
    assert records[0].last_restore_test == ""
