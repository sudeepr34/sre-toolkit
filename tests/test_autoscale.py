from sre_toolkit.autoscale import (
    check_autoscale,
    workloads_from_json,
    to_markdown,
    AutoscaleWorkload,
)


def _workload(**kwargs) -> AutoscaleWorkload:
    defaults = dict(
        deployment="api",
        namespace="prod",
        has_hpa=True,
        min_replicas=2,
        max_replicas=10,
        current_replicas=2,
        target_cpu_pct=70.0,
        current_cpu_pct=50.0,
        metric="cpu",
        owner="platform",
    )
    defaults.update(kwargs)
    return AutoscaleWorkload(**defaults)


def test_clean_ok():
    results = check_autoscale([_workload()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_no_hpa_blocked():
    results = check_autoscale([_workload(has_hpa=False)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no HPA"]


def test_min_equals_max_blocked():
    results = check_autoscale([_workload(min_replicas=3, max_replicas=3)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["min equals max (cannot scale)"]


def test_min_above_max_blocked():
    results = check_autoscale(
        [_workload(min_replicas=5, max_replicas=2, current_replicas=1)]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["min replicas above max replicas"]


def test_max_at_or_below_current_blocked():
    results = check_autoscale(
        [_workload(min_replicas=1, max_replicas=2, current_replicas=2)]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["max replicas at or below current replicas"]


def test_missing_target_risky():
    results = check_autoscale([_workload(target_cpu_pct=None)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no target CPU %"]


def test_missing_metric_risky():
    results = check_autoscale([_workload(metric="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no metric"]


def test_current_cpu_above_target_risky():
    results = check_autoscale([_workload(current_cpu_pct=85.0)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["current CPU above target"]


def test_missing_owner_risky():
    results = check_autoscale([_workload(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_blocked_beats_risky():
    results = check_autoscale([_workload(has_hpa=False, owner="")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no HPA", "no owner"]


def test_markdown_counts_and_sorted():
    workloads = [
        _workload(namespace="staging", deployment="web", has_hpa=False),
        _workload(),
    ]
    md = to_markdown(check_autoscale(workloads))
    assert "Workloads checked: 2" in md
    assert "Blocked: 1" in md
    assert "OK: 1" in md
    assert md.index("prod") < md.index("staging")
    assert "| staging | web | no | 2 | 10 | 70% | 50% | platform | blocked | no HPA |" in md
    assert "| prod | api | yes | 2 | 10 | 70% | 50% | platform | ok | — |" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "Workloads checked: 0" in md
    assert "No workloads to check." in md


def test_workloads_from_json_defaults():
    workloads = workloads_from_json(
        [{"namespace": "x", "deployment": "y"}]
    )
    assert workloads[0].has_hpa is False
    assert workloads[0].min_replicas == 1
    assert workloads[0].max_replicas == 1
    assert workloads[0].target_cpu_pct is None
    assert workloads[0].current_cpu_pct is None
    assert workloads[0].metric == ""
    assert workloads[0].owner == ""
