from sre_toolkit.namespace import (
    check_namespaces,
    namespaces_from_json,
    to_markdown,
    Namespace,
)


def _ns(**kwargs) -> Namespace:
    defaults = dict(
        name="prod",
        has_resource_quota=True,
        has_limit_range=True,
        has_network_policy=True,
        owner="platform",
    )
    defaults.update(kwargs)
    return Namespace(**defaults)


def test_clean_ok():
    results = check_namespaces([_ns()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_no_quota_blocked():
    results = check_namespaces([_ns(has_resource_quota=False)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no resource quota"]


def test_no_limit_range_risky():
    results = check_namespaces([_ns(has_limit_range=False)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no limit range"]


def test_no_network_policy_risky():
    results = check_namespaces([_ns(has_network_policy=False)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no network policy"]


def test_all_guards_missing():
    results = check_namespaces(
        [_ns(has_resource_quota=False, has_limit_range=False,
             has_network_policy=False)]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == [
        "no resource quota",
        "no limit range",
        "no network policy",
    ]


def test_missing_owner_risky():
    results = check_namespaces([_ns(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_blocked_beats_risky():
    results = check_namespaces(
        [_ns(has_resource_quota=False, owner="")]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no resource quota", "no owner"]


def test_markdown_counts_and_sorted():
    namespaces = [
        _ns(name="staging", has_resource_quota=False),
        _ns(),
    ]
    md = to_markdown(check_namespaces(namespaces))
    assert "Namespaces checked: 2" in md
    assert "Blocked: 1" in md
    assert "OK: 1" in md
    assert md.index("prod") < md.index("staging")
    assert "| staging | no | yes | yes | platform | blocked | no resource quota |" in md
    assert "| prod | yes | yes | yes | platform | ok | — |" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "Namespaces checked: 0" in md
    assert "No namespaces to check." in md


def test_namespaces_from_json_defaults():
    namespaces = namespaces_from_json([{"name": "x"}])
    assert namespaces[0].has_resource_quota is False
    assert namespaces[0].has_limit_range is False
    assert namespaces[0].has_network_policy is False
    assert namespaces[0].owner == ""
