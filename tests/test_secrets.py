from datetime import date

from sre_toolkit.secrets import (
    attention_needed,
    audit_issues,
    check_secrets,
    records_from_json,
    to_markdown,
    SecretRecord,
)

TODAY = date(2026, 11, 7)


def _secret(**kwargs) -> SecretRecord:
    defaults = dict(
        name="db-password", last_rotated="2026-10-01",
        rotation_days=90, owner="sre",
    )
    defaults.update(kwargs)
    return SecretRecord(**defaults)


def test_ok_secret():
    results = check_secrets([_secret()], TODAY)
    assert results[0].status == "ok"
    assert results[0].days_since_rotation == 37


def test_due_soon_secret():
    # 84 days old, 90-day rotation, 7-day window -> due
    results = check_secrets([_secret(last_rotated="2026-08-15")], TODAY)
    assert results[0].status == "due"


def test_overdue_secret():
    results = check_secrets([_secret(last_rotated="2026-07-01")], TODAY)
    assert results[0].status == "overdue"
    assert results[0].days_since_rotation == 129


def test_boundary_exactly_rotation_days_is_due():
    results = check_secrets([_secret(last_rotated="2026-08-09")], TODAY)
    assert results[0].status == "due"


def test_never_rotated_is_unknown():
    results = check_secrets([_secret(last_rotated="")], TODAY)
    assert results[0].status == "unknown"
    assert results[0].days_since_rotation is None


def test_bad_date_is_unknown():
    results = check_secrets([_secret(last_rotated="sometime")], TODAY)
    assert results[0].status == "unknown"


def test_audit_issues():
    records = [
        _secret(),
        _secret(name="api-key", last_rotated="2026-07-01"),
        _secret(name="token", owner="", last_rotated=""),
    ]
    issues = audit_issues(check_secrets(records, TODAY))
    assert [(i.name, i.kind) for i in issues] == [
        ("api-key", "overdue"),
        ("token", "owner"),
        ("token", "unknown"),
    ]
    assert "39 days" in issues[0].message


def test_attention_needed():
    assert attention_needed(check_secrets([_secret()], TODAY)) is False
    assert attention_needed(check_secrets([_secret(last_rotated="2026-08-15")], TODAY)) is False
    assert attention_needed(check_secrets([_secret(last_rotated="2026-07-01")], TODAY)) is True


def test_markdown_summary():
    records = [
        _secret(),
        _secret(name="api-key", last_rotated="2026-07-01"),
        _secret(name="token", owner="", last_rotated=""),
    ]
    results = check_secrets(records, TODAY)
    md = to_markdown(results, audit_issues(results))
    assert "Secrets checked: 3" in md
    assert "- Overdue: 1" in md
    assert "- Unknown: 1" in md
    assert "- OK: 1" in md
    assert "- Issues found: 3" in md
    assert "| api-key | 2026-07-01 | 129 | overdue |" in md
    assert "| token | owner | no owner team |" in md


def test_records_from_json_defaults():
    records = records_from_json([{"name": "x"}])
    assert records[0].last_rotated == ""
    assert records[0].rotation_days == 90
    assert records[0].owner == ""
