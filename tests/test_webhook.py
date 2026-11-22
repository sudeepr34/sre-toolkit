from sre_toolkit.webhook import (
    check_webhooks,
    webhooks_from_json,
    to_markdown,
    WebhookConfig,
)


def _wh(**kwargs) -> WebhookConfig:
    defaults = dict(
        name="image-policy",
        kind="validating",
        failure_policy="Ignore",
        timeout_seconds=10,
        ca_bundle=True,
        namespace_selector=True,
        owner="platform",
    )
    defaults.update(kwargs)
    return WebhookConfig(**defaults)


def test_clean_ok():
    results = check_webhooks([_wh()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_no_ca_bundle_blocked():
    results = check_webhooks([_wh(ca_bundle=False)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no caBundle"]


def test_timeout_out_of_range_blocked():
    results = check_webhooks([_wh(timeout_seconds=45)])
    assert results[0].verdict == "blocked"
    assert "timeout out of range" in results[0].issues
    assert "slow webhook" in results[0].issues


def test_unknown_failure_policy_blocked():
    results = check_webhooks([_wh(failure_policy="Maybe")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["unknown failurePolicy"]


def test_fail_closed_risky():
    results = check_webhooks([_wh(failure_policy="Fail")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["fail-closed stalls deploys"]


def test_slow_webhook_risky():
    results = check_webhooks([_wh(timeout_seconds=15)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["slow webhook"]


def test_mutating_without_selector_risky():
    results = check_webhooks(
        [_wh(kind="mutating", namespace_selector=False)]
    )
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no namespace selector"]


def test_no_owner_risky():
    results = check_webhooks([_wh(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_markdown_counts():
    results = check_webhooks(
        [_wh(), _wh(name="sidecar-inject", kind="mutating",
                    namespace_selector=False)]
    )
    out = to_markdown(results)
    assert "- Webhooks checked: 2" in out
    assert "- OK: 1" in out
    assert "- Risky: 1" in out
    assert "- Blocked: 0" in out
