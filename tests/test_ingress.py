from sre_toolkit.ingress import (
    check_ingresses,
    ingresses_from_json,
    to_markdown,
    Ingress,
)


def _ingress(**kwargs) -> Ingress:
    defaults = dict(
        name="api",
        namespace="prod",
        host="api.example.com",
        service="api",
        tls=True,
        owner="platform",
    )
    defaults.update(kwargs)
    return Ingress(**defaults)


def test_clean_ok():
    results = check_ingresses([_ingress()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_no_tls_blocked():
    results = check_ingresses([_ingress(tls=False)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no TLS"]


def test_no_service_blocked():
    results = check_ingresses([_ingress(service="")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no backend service"]


def test_no_host_blocked():
    results = check_ingresses([_ingress(host="")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no host"]


def test_duplicate_host_risky():
    results = check_ingresses([_ingress(), _ingress(name="api-2")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["duplicate host"]
    assert results[1].verdict == "risky"
    assert results[1].issues == ["duplicate host"]


def test_missing_owner_risky():
    results = check_ingresses([_ingress(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_blocked_beats_risky():
    results = check_ingresses(
        [_ingress(tls=False, owner=""), _ingress(name="api-2")]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no TLS", "duplicate host", "no owner"]


def test_markdown_counts_and_sorted():
    ingresses = [
        _ingress(namespace="staging", name="web", host="web.example.com",
                 service="web", tls=False),
        _ingress(),
    ]
    md = to_markdown(check_ingresses(ingresses))
    assert "Ingresses checked: 2" in md
    assert "Blocked: 1" in md
    assert "OK: 1" in md
    assert md.index("prod") < md.index("staging")
    assert "| staging | web | web.example.com | web | no | platform | blocked | no TLS |" in md
    assert "| prod | api | api.example.com | api | yes | platform | ok | — |" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "Ingresses checked: 0" in md
    assert "No ingresses to check." in md


def test_ingresses_from_json_defaults():
    ingresses = ingresses_from_json([{"name": "x", "namespace": "y"}])
    assert ingresses[0].host == ""
    assert ingresses[0].service == ""
    assert ingresses[0].tls is False
    assert ingresses[0].owner == ""
