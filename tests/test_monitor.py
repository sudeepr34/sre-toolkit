from sre_toolkit.monitor import (
    lint_rules,
    rules_from_json,
    to_markdown,
    AlertRule,
)


def _rule(**kwargs) -> AlertRule:
    defaults = dict(
        name="HighLatency", severity="critical",
        runbook="https://runbooks/latency", owner="sre",
    )
    defaults.update(kwargs)
    return AlertRule(**defaults)


def test_clean_rule_has_no_issues():
    assert lint_rules([_rule()]) == []


def test_missing_severity():
    issues = lint_rules([_rule(severity="")])
    assert [(i.rule, i.kind) for i in issues] == [("HighLatency", "severity")]
    assert "no severity" in issues[0].message


def test_unknown_severity():
    issues = lint_rules([_rule(severity="urgent")])
    assert issues[0].kind == "severity"
    assert "urgent" in issues[0].message


def test_severity_case_insensitive():
    assert lint_rules([_rule(severity="Critical")]) == []


def test_missing_runbook():
    issues = lint_rules([_rule(runbook="")])
    assert [(i.kind, i.message) for i in issues] == [("runbook", "no runbook link")]


def test_missing_owner():
    issues = lint_rules([_rule(owner="")])
    assert [i.kind for i in issues] == ["owner"]


def test_multiple_issues_per_rule():
    issues = lint_rules([_rule(severity="", runbook="", owner="")])
    assert [i.kind for i in issues] == ["severity", "runbook", "owner"]


def test_disabled_rule_skips_other_checks():
    issues = lint_rules([_rule(enabled=False, severity="", runbook="")])
    assert [(i.kind, i.message) for i in issues] == [("disabled", "rule is disabled")]


def test_duplicate_names():
    issues = lint_rules([_rule(), _rule()])
    assert [(i.kind, i.message) for i in issues] == [
        ("duplicate", "rule name appears 2 times")
    ]


def test_markdown_clean():
    md = to_markdown([_rule()], [])
    assert "Rules checked: 1" in md
    assert "Issues found: 0" in md
    assert "All rules clean" in md


def test_markdown_issues_table():
    rules = [_rule(severity=""), _rule(name="Down", runbook="")]
    md = to_markdown(rules, lint_rules(rules))
    assert "Issues found: 2" in md
    assert "- severity: 1" in md
    assert "| HighLatency | severity | no severity set |" in md
    assert "| Down | runbook | no runbook link |" in md


def test_rules_from_json_defaults():
    rules = rules_from_json([{"name": "x"}])
    assert rules[0].severity == ""
    assert rules[0].enabled is True
