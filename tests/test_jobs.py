from sre_toolkit.jobs import (
    check_jobs,
    jobs_from_json,
    to_markdown,
    CronJob,
)


def _job(**kwargs) -> CronJob:
    defaults = dict(
        name="backup",
        namespace="prod",
        schedule="0 2 * * *",
        last_success_hours_ago=5.0,
        failed_runs=0,
        suspended=False,
        owner="platform",
    )
    defaults.update(kwargs)
    return CronJob(**defaults)


def test_clean_ok():
    results = check_jobs([_job()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_no_schedule_blocked():
    results = check_jobs([_job(schedule="")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no schedule"]


def test_never_succeeded_blocked():
    results = check_jobs([_job(last_success_hours_ago=None)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["never succeeded"]


def test_failing_repeatedly_blocked():
    results = check_jobs([_job(failed_runs=3)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["3 failed runs"]


def test_some_failed_runs_risky():
    results = check_jobs([_job(failed_runs=1)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["1 failed runs"]


def test_stale_success_risky():
    results = check_jobs([_job(last_success_hours_ago=48.0)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["last success 48h ago"]


def test_custom_stale_threshold():
    results = check_jobs([_job(last_success_hours_ago=30.0)], stale_hours=48.0)
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_suspended_risky():
    results = check_jobs([_job(suspended=True)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["suspended"]


def test_missing_owner_risky():
    results = check_jobs([_job(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_blocked_beats_risky():
    results = check_jobs([_job(last_success_hours_ago=None, suspended=True)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["never succeeded", "suspended"]


def test_markdown_counts_and_sorted():
    jobs = [
        _job(namespace="staging", name="cleanup", last_success_hours_ago=None),
        _job(),
    ]
    md = to_markdown(check_jobs(jobs))
    assert "CronJobs checked: 2" in md
    assert "Blocked: 1" in md
    assert "OK: 1" in md
    assert md.index("prod") < md.index("staging")
    assert "| staging | cleanup | 0 2 * * * | never | 0 | no | platform | blocked | never succeeded |" in md
    assert "| prod | backup | 0 2 * * * | 5h ago | 0 | no | platform | ok | — |" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "CronJobs checked: 0" in md
    assert "No CronJobs to check." in md


def test_jobs_from_json_defaults():
    jobs = jobs_from_json([{"name": "x", "namespace": "y"}])
    assert jobs[0].schedule == ""
    assert jobs[0].last_success_hours_ago is None
    assert jobs[0].failed_runs == 0
    assert jobs[0].suspended is False
    assert jobs[0].owner == ""
