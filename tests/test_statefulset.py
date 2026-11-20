from sre_toolkit.statefulset import (
    check_stateful_sets,
    stateful_sets_from_json,
    to_markdown,
    StatefulSet,
)


def _sts(**kwargs) -> StatefulSet:
    defaults = dict(
        name="db",
        namespace="prod",
        replicas=3,
        ready_replicas=3,
        service_name="db-headless",
        volume_claim_templates=1,
        update_strategy="RollingUpdate",
        pod_management_policy="OrderedReady",
        owner="platform",
    )
    defaults.update(kwargs)
    return StatefulSet(**defaults)


def test_clean_ok():
    results = check_stateful_sets([_sts()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_no_headless_service_blocked():
    results = check_stateful_sets([_sts(service_name="")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no headless service"]


def test_no_volume_claims_blocked():
    results = check_stateful_sets([_sts(volume_claim_templates=0)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no volume claim templates"]


def test_not_fully_ready_blocked():
    results = check_stateful_sets([_sts(ready_replicas=2)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["not fully ready"]


def test_zero_replicas_not_blocked():
    results = check_stateful_sets(
        [_sts(replicas=0, ready_replicas=0)]
    )
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_on_delete_risky():
    results = check_stateful_sets([_sts(update_strategy="OnDelete")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["manual updates only"]


def test_parallel_management_risky():
    results = check_stateful_sets(
        [_sts(pod_management_policy="Parallel")]
    )
    assert results[0].verdict == "risky"
    assert results[0].issues == ["parallel pod management"]


def test_missing_owner_risky():
    results = check_stateful_sets([_sts(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_blocked_beats_risky():
    results = check_stateful_sets(
        [_sts(service_name="", owner="")]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no headless service", "no owner"]


def test_markdown_counts_and_sorted():
    sets = [
        _sts(namespace="staging", name="cache", service_name=""),
        _sts(),
    ]
    md = to_markdown(check_stateful_sets(sets))
    assert "StatefulSets checked: 2" in md
    assert "Blocked: 1" in md
    assert "OK: 1" in md
    assert md.index("prod") < md.index("staging")
    assert (
        "| staging | cache | 3 | 3 | — | 1 | RollingUpdate "
        "| OrderedReady | platform | blocked | no headless service |"
        in md
    )
    assert (
        "| prod | db | 3 | 3 | db-headless | 1 | RollingUpdate "
        "| OrderedReady | platform | ok | — |" in md
    )


def test_markdown_empty():
    md = to_markdown([])
    assert "StatefulSets checked: 0" in md
    assert "No StatefulSets to check." in md


def test_stateful_sets_from_json_defaults():
    sets = stateful_sets_from_json([{"name": "x", "namespace": "y"}])
    assert sets[0].replicas == 0
    assert sets[0].ready_replicas == 0
    assert sets[0].service_name == ""
    assert sets[0].volume_claim_templates == 0
    assert sets[0].update_strategy == "RollingUpdate"
    assert sets[0].pod_management_policy == "OrderedReady"
    assert sets[0].owner == ""
