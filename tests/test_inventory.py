from datetime import date

from sre_toolkit.inventory import (
    check_hosts,
    hosts_from_json,
    to_markdown,
    Host,
)

TODAY = date(2026, 11, 11)


def _host(**kwargs) -> Host:
    defaults = dict(
        name="web-01", owner="sre", environment="prod",
        patched=True, last_patched="2026-11-01",
    )
    defaults.update(kwargs)
    return Host(**defaults)


def test_clean_host():
    results = check_hosts([_host()], TODAY)
    assert results[0].issues == []


def test_missing_owner():
    results = check_hosts([_host(owner="")], TODAY)
    assert results[0].issues == ["missing owner"]


def test_unknown_environment():
    results = check_hosts([_host(environment="qa")], TODAY)
    assert results[0].issues == ["unknown environment"]


def test_unpatched():
    results = check_hosts([_host(patched=False)], TODAY)
    assert "unpatched" in results[0].issues


def test_patch_stale():
    results = check_hosts([_host(last_patched="2026-09-01")], TODAY)
    assert results[0].issues == ["patch stale"]


def test_patch_fresh_at_boundary():
    results = check_hosts([_host(last_patched="2026-10-12")], TODAY)
    assert results[0].issues == []


def test_unknown_patch_date_when_patched():
    results = check_hosts([_host(last_patched="")], TODAY)
    assert results[0].issues == ["unknown patch date"]


def test_multiple_issues_collected():
    results = check_hosts([_host(owner="", environment="qa", patched=False)], TODAY)
    assert results[0].issues == [
        "missing owner", "unknown environment", "unpatched",
    ]


def test_markdown_issues_table():
    hosts = [_host(), _host(name="db-01", owner="", patched=False, last_patched="")]
    md = to_markdown(check_hosts(hosts, TODAY))
    assert "Hosts checked: 2" in md
    assert "Hosts with issues: 1" in md
    assert "| db-01 | prod | — | missing owner, unpatched |" in md


def test_markdown_clean():
    md = to_markdown(check_hosts([_host()], TODAY))
    assert "Hosts with issues: 0" in md
    assert "Clean: every host has an owner" in md


def test_hosts_from_json_defaults():
    hosts = hosts_from_json([{"name": "x"}])
    assert hosts[0].owner == ""
    assert hosts[0].patched is False
