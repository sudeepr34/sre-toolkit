from sre_toolkit.network import (
    check_network,
    workloads_from_json,
    to_markdown,
    Workload,
)


def _workload(**kwargs) -> Workload:
    defaults = dict(
        namespace="prod",
        workload="api",
        pod_selector="app=api",
        has_policy=True,
        ingress=["10.0.0.0/8"],
        egress=["10.0.0.0/8"],
        default_deny=True,
        owner="platform",
    )
    defaults.update(kwargs)
    return Workload(**defaults)


def test_clean_ok():
    results = check_network([_workload()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_no_policy_blocked():
    results = check_network([_workload(has_policy=False)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no NetworkPolicy"]


def test_no_default_deny_risky():
    results = check_network([_workload(default_deny=False)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no default-deny policy"]


def test_allow_all_ingress_blocked():
    results = check_network([_workload(ingress=["0.0.0.0/0"])])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["allows all ingress (0.0.0.0/0)"]


def test_allow_all_egress_risky():
    results = check_network([_workload(egress=["0.0.0.0/0"])])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["allows all egress (0.0.0.0/0)"]


def test_missing_owner_risky():
    results = check_network([_workload(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_blocked_beats_risky():
    results = check_network(
        [_workload(has_policy=False, default_deny=False, owner="")]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no NetworkPolicy", "no owner"]


def test_markdown_counts_and_sorted():
    workloads = [
        _workload(namespace="staging", workload="web", has_policy=False),
        _workload(),
    ]
    md = to_markdown(check_network(workloads))
    assert "Workloads checked: 2" in md
    assert "Blocked: 1" in md
    assert "OK: 1" in md
    assert md.index("prod") < md.index("staging")
    assert "| staging | web | no | yes | platform | blocked | no NetworkPolicy |" in md
    assert "| prod | api | yes | yes | platform | ok | — |" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "Workloads checked: 0" in md
    assert "No workloads to check." in md


def test_workloads_from_json_defaults():
    workloads = workloads_from_json([{"namespace": "x", "workload": "y"}])
    assert workloads[0].has_policy is False
    assert workloads[0].default_deny is False
    assert workloads[0].ingress == []
    assert workloads[0].owner == ""
