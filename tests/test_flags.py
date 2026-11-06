from datetime import date

from sre_toolkit.flags import (
    audit_flags,
    flags_from_json,
    to_markdown,
    Flag,
)

TODAY = date(2026, 11, 6)


def _flag(**kwargs) -> Flag:
    defaults = dict(
        name="new-checkout", enabled=True, owner="sre",
        last_used="2026-11-05", created="2026-01-01",
    )
    defaults.update(kwargs)
    return Flag(**defaults)


def test_clean_flag_has_no_issues():
    assert audit_flags([_flag()], TODAY) == []


def test_missing_owner():
    issues = audit_flags([_flag(owner="")], TODAY)
    assert [(i.kind, i.message) for i in issues] == [("owner", "no owner team")]


def test_stale_flag():
    issues = audit_flags([_flag(last_used="2026-07-01")], TODAY)
    assert issues[0].kind == "stale"
    assert "128 days" in issues[0].message


def test_not_stale_within_threshold():
    assert audit_flags([_flag(last_used="2026-09-01")], TODAY) == []


def test_disabled_flag_not_stale():
    assert audit_flags([_flag(enabled=False, last_used="2025-01-01")], TODAY) == []


def test_never_used_falls_back_to_created():
    issues = audit_flags([_flag(last_used="", created="2025-01-01")], TODAY)
    assert [i.kind for i in issues] == ["stale"]


def test_enabled_no_dates_is_stale():
    issues = audit_flags([_flag(last_used="", created="")], TODAY)
    assert [i.kind for i in issues] == ["stale"]
    assert "no usage or creation date" in issues[0].message


def test_markdown_clean():
    md = to_markdown([_flag()], [])
    assert "Flags checked: 1" in md
    assert "Issues found: 0" in md
    assert "Flags clean" in md


def test_markdown_issues_table():
    flags = [_flag(owner=""), _flag(name="old", last_used="2026-01-01")]
    md = to_markdown(flags, audit_flags(flags, TODAY))
    assert "Issues found: 2" in md
    assert "- owner: 1" in md
    assert "- stale: 1" in md
    assert "| new-checkout | owner | no owner team |" in md


def test_flags_from_json_defaults():
    flags = flags_from_json([{"name": "x"}])
    assert flags[0].enabled is False
    assert flags[0].owner == ""
