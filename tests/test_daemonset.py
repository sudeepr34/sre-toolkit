from sre_toolkit.daemonset import (
    check_daemon_sets,
    daemon_sets_from_json,
    to_markdown,
    DaemonSet,
)


def _ds(**kwargs) -> DaemonSet:
    defaults = dict(
        name="node-agent",
        namespace="kube-system",
        desired=5,
        ready=5,
        misscheduled=0,
        update_strategy="RollingUpdate",
        owner="platform",
    )
    defaults.update(kwargs)
    return DaemonSet(**defaults)


def test_clean_ok():
    results = check_daemon_sets([_ds()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_not_fully_ready_blocked():
    results = check_daemon_sets([_ds(ready=4)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["not fully ready"]


def test_misscheduled_blocked():
    results = check_daemon_sets([_ds(misscheduled=2)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["pods misscheduled"]


def test_zero_desired_not_blocked():
    results = check_daemon_sets([_ds(desired=0, ready=0)])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_on_delete_risky():
    results = check_daemon_sets([_ds(update_strategy="OnDelete")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["manual updates only"]


def test_missing_owner_risky():
    results = check_daemon_sets([_ds(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_blocked_beats_risky():
    results = check_daemon_sets([_ds(ready=3, owner="")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["not fully ready", "no owner"]


def test_markdown_counts_and_sorted():
    sets = [
        _ds(namespace="prod", name="agent", ready=4),
        _ds(),
    ]
    md = to_markdown(check_daemon_sets(sets))
    assert "DaemonSets checked: 2" in md
    assert "Blocked: 1" in md
    assert "OK: 1" in md
    assert md.index("kube-system") < md.index("prod")
    assert (
        "| prod | agent | 5 | 4 | 0 | RollingUpdate "
        "| platform | blocked | not fully ready |" in md
    )
    assert (
        "| kube-system | node-agent | 5 | 5 | 0 | RollingUpdate "
        "| platform | ok | — |" in md
    )


def test_markdown_empty():
    md = to_markdown([])
    assert "DaemonSets checked: 0" in md
    assert "No DaemonSets to check." in md


def test_daemon_sets_from_json_defaults():
    sets = daemon_sets_from_json([{"name": "x", "namespace": "y"}])
    assert sets[0].desired == 0
    assert sets[0].ready == 0
    assert sets[0].misscheduled == 0
    assert sets[0].update_strategy == "RollingUpdate"
    assert sets[0].owner == ""
