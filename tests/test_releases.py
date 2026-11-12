from datetime import date

from sre_toolkit.releases import (
    check_releases,
    releases_from_json,
    to_markdown,
    Release,
)

TODAY = date(2026, 11, 12)


def _release(service: str, version: str, date_: str) -> Release:
    return Release(version, service, date_)


def test_fresh_service_not_stale():
    results = check_releases([_release("api", "v1.4.2", "2026-11-10")], TODAY)
    assert len(results) == 1
    assert results[0].service == "api"
    assert results[0].last_version == "v1.4.2"
    assert results[0].days_since == 2
    assert results[0].stale is False


def test_stale_service():
    results = check_releases([_release("api", "v1.0.0", "2026-09-01")], TODAY)
    assert results[0].days_since == 72
    assert results[0].stale is True


def test_boundary_exactly_stale_days_not_stale():
    results = check_releases([_release("api", "v1.0.0", "2026-10-13")], TODAY)
    assert results[0].days_since == 30
    assert results[0].stale is False


def test_latest_release_wins():
    releases = [
        _release("api", "v1.0.0", "2026-09-01"),
        _release("api", "v1.2.0", "2026-11-05"),
        _release("api", "v1.1.0", "2026-10-01"),
    ]
    results = check_releases(releases, TODAY)
    assert results[0].last_version == "v1.2.0"
    assert results[0].days_since == 7


def test_bad_dates_ignored():
    results = check_releases([_release("api", "v1.0.0", "soon")], TODAY)
    assert results == []


def test_multiple_services():
    releases = [
        _release("api", "v1.2.0", "2026-11-05"),
        _release("db", "v3.0.0", "2026-08-01"),
    ]
    results = check_releases(releases, TODAY)
    assert [r.service for r in results] == ["api", "db"]
    assert [r.stale for r in results] == [False, True]


def test_custom_stale_threshold():
    results = check_releases([_release("api", "v1.0.0", "2026-10-28")], TODAY, stale_days=14)
    assert results[0].days_since == 15
    assert results[0].stale is True


def test_markdown_sorted_stalest_first():
    releases = [
        _release("api", "v1.2.0", "2026-11-05"),
        _release("db", "v3.0.0", "2026-08-01"),
    ]
    md = to_markdown(check_releases(releases, TODAY))
    assert "Services checked: 2" in md
    assert "Stale services: 1" in md
    assert md.index("db") < md.index("api")
    assert "| db | v3.0.0 | 2026-08-01 | 103 | yes |" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "Services checked: 0" in md
    assert "No releases to check." in md


def test_releases_from_json_defaults():
    releases = releases_from_json([{"version": "v1"}])
    assert releases[0].service == "unnamed"
    assert releases[0].date == ""
