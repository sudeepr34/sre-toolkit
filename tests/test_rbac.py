from sre_toolkit.rbac import (
    bindings_from_json,
    check_bindings,
    to_markdown,
    RoleBinding,
)


def _binding(**kwargs) -> RoleBinding:
    defaults = dict(
        name="deployer",
        namespace="prod",
        subject_kind="ServiceAccount",
        subject_name="deployer",
        role="deploy",
        verbs=["get", "list"],
        resources=["deployments"],
        owner="platform",
    )
    defaults.update(kwargs)
    return RoleBinding(**defaults)


def test_clean_ok():
    results = check_bindings([_binding()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_cluster_admin_blocked():
    results = check_bindings([_binding(role="cluster-admin")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["cluster-admin role"]


def test_wildcard_verb_blocked():
    results = check_bindings([_binding(verbs=["*"])])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["wildcard verb"]


def test_wildcard_resource_risky():
    results = check_bindings([_binding(resources=["*"])])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["wildcard resource"]


def test_service_account_no_owner_risky():
    results = check_bindings([_binding(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["service account with no owner"]


def test_user_no_owner_risky():
    results = check_bindings(
        [_binding(subject_kind="User", subject_name="alice", owner="")]
    )
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_blocked_beats_risky():
    results = check_bindings(
        [_binding(role="cluster-admin", resources=["*"], owner="")]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == [
        "cluster-admin role",
        "wildcard resource",
        "service account with no owner",
    ]


def test_markdown_counts_and_sorted():
    bindings = [
        _binding(
            namespace="staging",
            name="admin",
            role="cluster-admin",
        ),
        _binding(),
    ]
    md = to_markdown(check_bindings(bindings))
    assert "Bindings checked: 2" in md
    assert "Blocked: 1" in md
    assert "OK: 1" in md
    assert md.index("prod") < md.index("staging")
    assert (
        "| prod | deployer | ServiceAccount:deployer | deploy | "
        "platform | ok | — |" in md
    )


def test_markdown_empty():
    md = to_markdown([])
    assert "Bindings checked: 0" in md
    assert "No bindings to check." in md


def test_bindings_from_json_defaults():
    bindings = bindings_from_json([{"name": "x", "namespace": "y"}])
    assert bindings[0].role == ""
    assert bindings[0].verbs == []
    assert bindings[0].owner == ""
