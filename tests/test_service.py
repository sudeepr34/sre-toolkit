from sre_toolkit.service import (
    audit_services,
    services_from_json,
    to_markdown,
    ServiceEntry,
)


def _service(**kwargs) -> ServiceEntry:
    defaults = dict(
        name="api", owner="sre", tier="critical",
        runbook="https://runbooks/api",
    )
    defaults.update(kwargs)
    return ServiceEntry(**defaults)


def test_clean_service_has_no_issues():
    assert audit_services([_service()]) == []


def test_missing_owner():
    issues = audit_services([_service(owner="")])
    assert [(i.kind, i.message) for i in issues] == [("owner", "no owner team")]


def test_missing_tier():
    issues = audit_services([_service(tier="")])
    assert [(i.kind, i.message) for i in issues] == [("tier", "no tier set")]


def test_unknown_tier():
    issues = audit_services([_service(tier="mega")])
    assert issues[0].kind == "tier"
    assert "mega" in issues[0].message


def test_tier_case_insensitive():
    assert audit_services([_service(tier="Critical")]) == []


def test_missing_runbook():
    issues = audit_services([_service(runbook="")])
    assert [i.kind for i in issues] == ["runbook"]


def test_multiple_issues_per_service():
    issues = audit_services([_service(owner="", tier="", runbook="")])
    assert [i.kind for i in issues] == ["owner", "tier", "runbook"]


def test_markdown_clean():
    md = to_markdown([_service()], [])
    assert "Services checked: 1" in md
    assert "Issues found: 0" in md
    assert "Catalog clean" in md


def test_markdown_issues_table():
    services = [_service(owner=""), _service(name="db", tier="mega")]
    md = to_markdown(services, audit_services(services))
    assert "Issues found: 2" in md
    assert "- owner: 1" in md
    assert "- tier: 1" in md
    assert "| api | owner | no owner team |" in md
    assert "| db | tier | unknown tier 'mega' |" in md


def test_services_from_json_defaults():
    services = services_from_json([{"name": "x"}])
    assert services[0].owner == ""
    assert services[0].tier == ""
    assert services[0].runbook == ""
