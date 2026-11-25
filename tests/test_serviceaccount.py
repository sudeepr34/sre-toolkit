from sre_toolkit.serviceaccount import (
    check_service_accounts,
    service_accounts_from_json,
    to_markdown,
    ServiceAccount,
)


def _sa(**kwargs) -> ServiceAccount:
    defaults = dict(
        name="api",
        namespace="prod",
        is_default=False,
        automount_token=False,
        cluster_roles=[],
        owner="platform",
    )
    defaults.update(kwargs)
    return ServiceAccount(**defaults)


def test_clean_ok():
    results = check_service_accounts([_sa()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_cluster_admin_blocked():
    results = check_service_accounts(
        [_sa(cluster_roles=["cluster-admin"])]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["bound to cluster-admin"]


def test_automount_token_risky():
    results = check_service_accounts([_sa(automount_token=True)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["token auto-mounted"]


def test_default_account_risky():
    results = check_service_accounts([_sa(is_default=True)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["default service account in use"]


def test_missing_owner_risky():
    results = check_service_accounts([_sa(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_blocked_beats_risky():
    results = check_service_accounts(
        [_sa(cluster_roles=["cluster-admin"], automount_token=True, owner="")]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == [
        "bound to cluster-admin",
        "token auto-mounted",
        "no owner",
    ]


def test_other_cluster_role_not_blocked():
    results = check_service_accounts(
        [_sa(cluster_roles=["view"])]
    )
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_markdown_counts_and_sorted():
    accounts = [
        _sa(name="deployer", cluster_roles=["cluster-admin"]),
        _sa(),
    ]
    md = to_markdown(check_service_accounts(accounts))
    assert "Service accounts checked: 2" in md
    assert "Blocked: 1" in md
    assert "OK: 1" in md
    assert md.index("api") < md.index("deployer")
    assert (
        "| deployer | prod | no | no | cluster-admin | platform | blocked |"
        " bound to cluster-admin |" in md
    )
    assert "| api | prod | no | no | — | platform | ok | — |" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "Service accounts checked: 0" in md
    assert "No service accounts to check." in md


def test_service_accounts_from_json_defaults():
    accounts = service_accounts_from_json([{"name": "x"}])
    assert accounts[0].namespace == "default"
    assert accounts[0].is_default is False
    assert accounts[0].automount_token is True
    assert accounts[0].cluster_roles == []
    assert accounts[0].owner == ""
