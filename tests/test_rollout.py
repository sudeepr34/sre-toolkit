from datetime import datetime

from sre_toolkit.rollout import check_rollouts, rollouts_from_json, to_markdown, Rollout

NOW = datetime.fromisoformat("2026-11-05T12:00")


def _rollout(**kwargs) -> Rollout:
    defaults = dict(name="api-v2", service="api", status="progressing",
                    started="2026-11-05T11:45", deadline_minutes=30,
                    progress_pct=50)
    defaults.update(kwargs)
    return Rollout(**defaults)


def test_complete_is_ok():
    results = check_rollouts([_rollout(status="complete", progress_pct=100)], now=NOW)
    assert results[0].status == "ok"
    assert "complete" in results[0].detail


def test_progressing_within_deadline_is_ok():
    results = check_rollouts([_rollout()], now=NOW)
    assert results[0].status == "ok"
    assert "15m in" in results[0].detail


def test_progressing_past_deadline_is_stuck():
    results = check_rollouts(
        [_rollout(started="2026-11-05T11:00")], now=NOW
    )
    assert results[0].status == "stuck"
    assert "60m past 30m deadline" in results[0].detail


def test_exactly_at_deadline_is_ok():
    results = check_rollouts(
        [_rollout(started="2026-11-05T11:30")], now=NOW
    )
    assert results[0].status == "ok"


def test_failed_is_failed():
    results = check_rollouts([_rollout(status="failed")], now=NOW)
    assert results[0].status == "failed"


def test_unreadable_started_is_stuck():
    results = check_rollouts([_rollout(started="soon")], now=NOW)
    assert results[0].status == "stuck"
    assert "unreadable" in results[0].detail


def test_unknown_status_is_stuck():
    results = check_rollouts([_rollout(status="vibing")], now=NOW)
    assert results[0].status == "stuck"


def test_markdown_lists_problems():
    results = check_rollouts(
        [_rollout(status="complete", progress_pct=100),
         _rollout(name="db-v3", started="2026-11-05T11:00")],
        now=NOW,
    )
    md = to_markdown(results)
    assert "# Rollout status" in md
    assert "Checked 2 rollouts: 1 ok, 1 stuck" in md
    assert "| db-v3 | api | stuck |" in md
    assert "## Needs attention" in md


def test_markdown_all_healthy():
    md = to_markdown(check_rollouts([_rollout(status="complete", progress_pct=100)], now=NOW))
    assert "All rollouts healthy." in md


def test_rollouts_from_json_defaults():
    rollouts = rollouts_from_json([{"name": "x"}])
    assert rollouts[0].status == "progressing"
    assert rollouts[0].deadline_minutes == 30
