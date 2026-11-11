import pytest

from sre_toolkit.pods import (
    check_pods,
    pods_from_json,
    restarts_per_day,
    to_markdown,
    Pod,
)


def _pod(**kwargs) -> Pod:
    defaults = dict(name="api-abc", namespace="prod", restarts=0, age_hours=48.0)
    defaults.update(kwargs)
    return Pod(**defaults)


def test_ok_pod():
    results = check_pods([_pod()])
    assert results[0].status == "ok"
    assert results[0].restarts_per_day == pytest.approx(0.0)


def test_warning_pod():
    results = check_pods([_pod(restarts=2)])
    assert results[0].status == "warning"


def test_critical_pod_at_threshold():
    results = check_pods([_pod(restarts=5)])
    assert results[0].status == "critical"


def test_restarts_per_day():
    assert restarts_per_day(_pod(restarts=12, age_hours=48.0)) == pytest.approx(6.0)


def test_restarts_per_day_unknown_age():
    assert restarts_per_day(_pod(restarts=3, age_hours=0)) is None


def test_markdown_sorted_most_restarts_first():
    pods = [
        _pod(name="stable", restarts=0),
        _pod(name="flapping", restarts=12, age_hours=24.0),
        _pod(name="wobbly", restarts=2),
    ]
    md = to_markdown(check_pods(pods))
    assert "Pods checked: 3" in md
    assert "- Critical: 1" in md
    assert "- Warning: 1" in md
    assert "- OK: 1" in md
    assert md.index("flapping") < md.index("wobbly") < md.index("stable")
    assert "| flapping | prod | 12 | 12.0 | critical |" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "Pods checked: 0" in md
    assert "No pods to check." in md


def test_pods_from_json_defaults():
    pods = pods_from_json([{"name": "x"}])
    assert pods[0].namespace == "default"
    assert pods[0].restarts == 0
    assert pods[0].age_hours == 0.0
