from sre_toolkit.endpoints import (
    check_endpoints,
    endpoints_from_json,
    to_markdown,
    Endpoints,
)


def _service(**kwargs) -> Endpoints:
    defaults = dict(
        name="api",
        namespace="prod",
        ready_endpoints=3,
        total_endpoints=3,
        owner="platform",
    )
    defaults.update(kwargs)
    return Endpoints(**defaults)


def test_clean_ok():
    results = check_endpoints([_service()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_no_ready_endpoints_blocked():
    results = check_endpoints([_service(ready_endpoints=0, total_endpoints=3)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no ready endpoints"]


def test_no_endpoints_at_all_blocked():
    results = check_endpoints([_service(ready_endpoints=0, total_endpoints=0)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no ready endpoints"]


def test_partial_readiness_risky():
    results = check_endpoints([_service(ready_endpoints=2, total_endpoints=3)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["partial readiness"]


def test_single_ready_endpoint_risky():
    results = check_endpoints([_service(ready_endpoints=1, total_endpoints=1)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["single ready endpoint"]


def test_missing_owner_risky():
    results = check_endpoints([_service(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_blocked_beats_risky():
    results = check_endpoints(
        [_service(ready_endpoints=0, total_endpoints=2, owner="")]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no ready endpoints", "no owner"]


def test_markdown_counts():
    results = check_endpoints(
        [_service(), _service(name="web", ready_endpoints=0, total_endpoints=2)]
    )
    report = to_markdown(results)
    assert "- Services checked: 2" in report
    assert "- OK: 1" in report
    assert "- Blocked: 1" in report
    assert "| web | prod | 0 | 2 | platform | blocked | no ready endpoints |" in report


def test_from_json_defaults():
    services = endpoints_from_json([{"name": "api"}])
    assert services[0].namespace == "default"
    assert services[0].ready_endpoints == 0
    assert services[0].total_endpoints == 0
    assert services[0].owner == ""
