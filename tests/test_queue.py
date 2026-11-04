from sre_toolkit.queue import (
    check_queues,
    snapshots_from_json,
    to_markdown,
    QueueSnapshot,
)


def _snap(**kwargs) -> QueueSnapshot:
    defaults = dict(queue="jobs", depth=100, oldest_age_minutes=10,
                    max_depth=1000, max_age_minutes=60)
    defaults.update(kwargs)
    return QueueSnapshot(**defaults)


def test_ok_when_within_thresholds():
    results = check_queues([_snap()])
    assert results[0].status == "ok"
    assert "depth 100 (max 1000)" in results[0].detail


def test_exactly_at_threshold_is_ok():
    results = check_queues([_snap(depth=1000, oldest_age_minutes=60)])
    assert results[0].status == "ok"


def test_depth_breach():
    results = check_queues([_snap(depth=1500)])
    assert results[0].status == "breach"
    assert "depth 1500 over max 1000" in results[0].detail


def test_age_breach():
    results = check_queues([_snap(oldest_age_minutes=90)])
    assert results[0].status == "breach"
    assert "oldest item 90m over max 60m" in results[0].detail


def test_both_breaches_listed():
    results = check_queues([_snap(depth=1500, oldest_age_minutes=90)])
    assert results[0].status == "breach"
    assert "depth 1500 over max 1000" in results[0].detail
    assert "oldest item 90m over max 60m" in results[0].detail


def test_markdown_lists_breaches():
    results = check_queues([_snap(), _snap(queue="events", depth=2000)])
    md = to_markdown(results)
    assert "# Queue backlog" in md
    assert "Checked 2 queues: 1 breach, 1 ok" in md
    assert "| events | breach | depth 2000 over max 1000 |" in md
    assert "## Breaches" in md
    assert "- events: depth 2000 over max 1000" in md


def test_markdown_all_within_message():
    md = to_markdown(check_queues([_snap()]))
    assert "All queues within thresholds." in md


def test_snapshots_from_json_defaults():
    snaps = snapshots_from_json([{"queue": "x"}])
    assert snaps[0].depth == 0
    assert snaps[0].max_depth == 1000
    assert snaps[0].max_age_minutes == 60
