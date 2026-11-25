from sre_toolkit.podsecurity import (
    check_pod_security,
    pod_security_from_json,
    to_markdown,
    PodSecurity,
)


def _pod(**kwargs) -> PodSecurity:
    defaults = dict(
        name="api",
        namespace="prod",
        privileged=False,
        host_network=False,
        host_pid=False,
        run_as_root=False,
        allow_privilege_escalation=False,
        read_only_root_filesystem=True,
        owner="platform",
    )
    defaults.update(kwargs)
    return PodSecurity(**defaults)


def test_clean_ok():
    results = check_pod_security([_pod()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_privileged_blocked():
    results = check_pod_security([_pod(privileged=True)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["privileged"]


def test_host_network_blocked():
    results = check_pod_security([_pod(host_network=True)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["host network"]


def test_host_pid_blocked():
    results = check_pod_security([_pod(host_pid=True)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["host PID namespace"]


def test_run_as_root_risky():
    results = check_pod_security([_pod(run_as_root=True)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["runs as root"]


def test_privilege_escalation_risky():
    results = check_pod_security([_pod(allow_privilege_escalation=True)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["privilege escalation allowed"]


def test_writable_rootfs_risky():
    results = check_pod_security([_pod(read_only_root_filesystem=False)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["writable root filesystem"]


def test_missing_owner_risky():
    results = check_pod_security([_pod(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_blocked_beats_risky():
    results = check_pod_security(
        [_pod(privileged=True, run_as_root=True, owner="")]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == [
        "privileged",
        "runs as root",
        "no owner",
    ]


def test_markdown_counts_and_sorted():
    pods = [
        _pod(name="debug", privileged=True),
        _pod(),
    ]
    md = to_markdown(check_pod_security(pods))
    assert "Pods checked: 2" in md
    assert "Blocked: 1" in md
    assert "OK: 1" in md
    assert md.index("api") < md.index("debug")
    assert (
        "| debug | prod | yes | no | no | no | no | yes | platform |"
        " blocked | privileged |" in md
    )
    assert "| api | prod | no | no | no | no | no | yes | platform | ok | — |" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "Pods checked: 0" in md
    assert "No pods to check." in md


def test_pod_security_from_json_defaults():
    pods = pod_security_from_json([{"name": "x"}])
    assert pods[0].namespace == "default"
    assert pods[0].privileged is False
    assert pods[0].host_network is False
    assert pods[0].host_pid is False
    assert pods[0].run_as_root is False
    assert pods[0].allow_privilege_escalation is False
    assert pods[0].read_only_root_filesystem is False
    assert pods[0].owner == ""
