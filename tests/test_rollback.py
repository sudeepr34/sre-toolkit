from sre_toolkit.rollback import (
    check_rollback,
    ready_count,
    records_from_json,
    to_markdown,
    DeployRecord,
)


def _deploy(**kwargs) -> DeployRecord:
    defaults = dict(
        service="api", version="v2.1.0", previous_version="v2.0.9",
        rollback_runbook="https://runbooks/rollback-api",
        rollback_tested=True,
    )
    defaults.update(kwargs)
    return DeployRecord(**defaults)


def test_ready_deploy_has_no_issues():
    assert check_rollback([_deploy()]) == []


def test_missing_previous_version():
    issues = check_rollback([_deploy(previous_version="")])
    assert [(i.kind, i.message) for i in issues] == [
        ("previous_version", "no previous version to roll back to")
    ]


def test_missing_runbook():
    issues = check_rollback([_deploy(rollback_runbook="")])
    assert [i.kind for i in issues] == ["runbook"]


def test_untested_rollback():
    issues = check_rollback([_deploy(rollback_tested=False)])
    assert [(i.kind, i.message) for i in issues] == [
        ("untested", "rollback never tested")
    ]


def test_multiple_issues_per_deploy():
    issues = check_rollback([
        _deploy(previous_version="", rollback_runbook="", rollback_tested=False)
    ])
    assert [i.kind for i in issues] == ["previous_version", "runbook", "untested"]


def test_ready_count():
    deploys = [_deploy(), _deploy(version="v2.2.0", rollback_tested=False)]
    issues = check_rollback(deploys)
    assert ready_count(deploys, issues) == 1


def test_markdown_clean():
    md = to_markdown([_deploy()], [])
    assert "Deploys checked: 1" in md
    assert "Ready to roll back: 1" in md
    assert "Issues found: 0" in md
    assert "All deploys are rollback-ready" in md


def test_markdown_issues_table():
    deploys = [_deploy(rollback_tested=False), _deploy(service="db", previous_version="")]
    md = to_markdown(deploys, check_rollback(deploys))
    assert "Issues found: 2" in md
    assert "- untested: 1" in md
    assert "- previous_version: 1" in md
    assert "| api | v2.1.0 | untested | rollback never tested |" in md
    assert "| db | v2.1.0 | previous_version | no previous version to roll back to |" in md


def test_records_from_json_defaults():
    records = records_from_json([{"service": "x", "version": "v1"}])
    assert records[0].previous_version == ""
    assert records[0].rollback_runbook == ""
    assert records[0].rollback_tested is False
