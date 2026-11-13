import pytest

from sre_toolkit.replicas import (
    check_replicas,
    deployments_from_json,
    to_markdown,
    Deployment,
)


def _deployment(**kwargs) -> Deployment:
    defaults = dict(name="api", namespace="prod", desired=3, ready=3)
    defaults.update(kwargs)
    return Deployment(**defaults)


def test_ok_deployment():
    results = check_replicas([_deployment()])
    assert results[0].status == "ok"
    assert results[0].ready_pct == pytest.approx(100.0)


def test_degraded_deployment():
    results = check_replicas([_deployment(ready=2)])
    assert results[0].status == "degraded"
    assert results[0].ready_pct == pytest.approx(66.7, abs=0.1)


def test_down_deployment():
    results = check_replicas([_deployment(ready=0)])
    assert results[0].status == "down"
    assert results[0].ready_pct == pytest.approx(0.0)


def test_over_replicated_is_ok():
    results = check_replicas([_deployment(ready=4)])
    assert results[0].status == "ok"


def test_zero_desired_unknown_pct():
    results = check_replicas([_deployment(desired=0, ready=0)])
    assert results[0].ready_pct is None
    assert results[0].status == "down"


def test_markdown_sorted_by_name():
    deployments = [
        _deployment(name="web", desired=2, ready=1),
        _deployment(name="api", desired=3, ready=0),
        _deployment(name="db", desired=1, ready=1),
    ]
    md = to_markdown(check_replicas(deployments))
    assert "Deployments checked: 3" in md
    assert "- OK: 1" in md
    assert "- Degraded: 1" in md
    assert "- Down: 1" in md
    assert md.index("api") < md.index("db") < md.index("web")
    assert "| api | prod | 3 | 0 | 0.0 | down |" in md
    assert "| web | prod | 2 | 1 | 50.0 | degraded |" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "Deployments checked: 0" in md
    assert "No deployments to check." in md


def test_deployments_from_json_defaults():
    deployments = deployments_from_json([{"name": "x"}])
    assert deployments[0].namespace == "default"
    assert deployments[0].desired == 1
    assert deployments[0].ready == 0
