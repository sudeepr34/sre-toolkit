from datetime import date

from sre_toolkit.migrations import (
    check_migrations,
    migrations_from_json,
    to_markdown,
    Migration,
)

TODAY = date(2026, 11, 12)


def _migration(**kwargs) -> Migration:
    defaults = dict(
        id="20261101001", service="api", status="applied",
        created="2026-11-01", applied_at="2026-11-02",
    )
    defaults.update(kwargs)
    return Migration(**defaults)


def test_applied_clean():
    results = check_migrations([_migration()], TODAY)
    assert results[0].days_pending is None
    assert results[0].stale is False


def test_pending_not_stale():
    results = check_migrations(
        [_migration(id="m1", status="pending", created="2026-11-05")], TODAY
    )
    assert results[0].days_pending == 7
    assert results[0].stale is False


def test_pending_stale():
    results = check_migrations(
        [_migration(id="m1", status="pending", created="2026-10-20")], TODAY
    )
    assert results[0].days_pending == 23
    assert results[0].stale is True


def test_pending_boundary_exactly_stale_days_not_stale():
    results = check_migrations(
        [_migration(id="m1", status="pending", created="2026-10-29")], TODAY
    )
    assert results[0].days_pending == 14
    assert results[0].stale is False


def test_failed_no_days_pending():
    results = check_migrations([_migration(id="m1", status="failed")], TODAY)
    assert results[0].days_pending is None
    assert results[0].stale is False


def test_pending_bad_created_date():
    results = check_migrations(
        [_migration(id="m1", status="pending", created="sometime")], TODAY
    )
    assert results[0].days_pending is None
    assert results[0].stale is False


def test_markdown_attention_sorted_failed_first():
    migrations = [
        _migration(id="m1", status="pending", created="2026-11-05"),
        _migration(id="m2", status="failed"),
        _migration(id="m3", status="applied"),
    ]
    md = to_markdown(check_migrations(migrations, TODAY))
    assert "Migrations checked: 3" in md
    assert "- Applied: 1" in md
    assert "- Pending: 1" in md
    assert "- Failed: 1" in md
    assert "- Stale pending: 0" in md
    assert md.index("m2") < md.index("m1")
    assert "| m2 | api | failed | n/a |" in md
    assert "| m1 | api | pending | 7 |" in md


def test_markdown_clean():
    md = to_markdown(check_migrations([_migration()], TODAY))
    assert "Pending: 0" in md
    assert "Clean: every migration is applied" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "Migrations checked: 0" in md


def test_migrations_from_json_defaults():
    migrations = migrations_from_json([{"id": "m1"}])
    assert migrations[0].service == "unnamed"
    assert migrations[0].status == "pending"
