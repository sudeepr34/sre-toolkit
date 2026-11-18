from sre_toolkit.cron import (
    check_crons,
    crons_from_json,
    is_valid_schedule,
    to_markdown,
    CronSchedule,
)


def _cron(**kwargs) -> CronSchedule:
    defaults = dict(
        name="backup",
        namespace="prod",
        schedule="0 2 * * *",
        owner="platform",
    )
    defaults.update(kwargs)
    return CronSchedule(**defaults)


def test_clean_ok():
    results = check_crons([_cron()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_no_schedule_blocked():
    results = check_crons([_cron(schedule="")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no schedule"]


def test_wrong_field_count_blocked():
    results = check_crons([_cron(schedule="0 2 * *")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["invalid schedule"]


def test_minute_out_of_range_blocked():
    results = check_crons([_cron(schedule="61 2 * * *")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["invalid schedule"]


def test_month_out_of_range_blocked():
    results = check_crons([_cron(schedule="0 2 * 13 *")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["invalid schedule"]


def test_zero_step_blocked():
    results = check_crons([_cron(schedule="*/0 2 * * *")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["invalid schedule"]


def test_every_minute_risky():
    results = check_crons([_cron(schedule="* * * * *")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["runs every minute"]


def test_every_minute_step_risky():
    results = check_crons([_cron(schedule="*/1 * * * *")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["runs every minute"]


def test_duplicate_schedule_risky():
    results = check_crons([_cron(), _cron(name="backup-2")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["duplicate schedule"]
    assert results[1].verdict == "risky"
    assert results[1].issues == ["duplicate schedule"]


def test_missing_owner_risky():
    results = check_crons([_cron(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_blocked_beats_risky():
    results = check_crons([_cron(schedule="61 2 * * *", owner="")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["invalid schedule", "no owner"]


def test_named_month_and_dow_ok():
    assert is_valid_schedule("0 2 * JAN MON") is True
    results = check_crons([_cron(schedule="0 2 * JAN MON")])
    assert results[0].verdict == "ok"


def test_step_and_list_ok():
    assert is_valid_schedule("0 */6 * * 1,3,5") is True
    results = check_crons([_cron(schedule="0 */6 * * 1,3,5")])
    assert results[0].verdict == "ok"


def test_range_ok():
    assert is_valid_schedule("0 9-17 * * 1-5") is True


def test_markdown_counts_and_sorted():
    crons = [
        _cron(namespace="staging", name="cleanup", schedule="61 2 * * *"),
        _cron(),
    ]
    md = to_markdown(check_crons(crons))
    assert "Schedules checked: 2" in md
    assert "Blocked: 1" in md
    assert "OK: 1" in md
    assert md.index("prod") < md.index("staging")
    assert "| staging | cleanup | 61 2 * * * | platform | blocked | invalid schedule |" in md
    assert "| prod | backup | 0 2 * * * | platform | ok | — |" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "Schedules checked: 0" in md
    assert "No schedules to check." in md


def test_crons_from_json_defaults():
    crons = crons_from_json([{"name": "x", "namespace": "y"}])
    assert crons[0].schedule == ""
    assert crons[0].owner == ""
