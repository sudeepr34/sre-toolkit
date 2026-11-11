from sre_toolkit.change import (
    changes_from_json,
    find_collisions,
    to_markdown,
    Change,
)


def _change(id: str, service: str, start: str, end: str) -> Change:
    return Change(id, service, start, end)


def test_no_collision_different_services():
    changes = [
        _change("c1", "api", "2026-11-12T02:00:00", "2026-11-12T04:00:00"),
        _change("c2", "db", "2026-11-12T03:00:00", "2026-11-12T05:00:00"),
    ]
    assert find_collisions(changes) == []


def test_no_collision_same_service_disjoint():
    changes = [
        _change("c1", "api", "2026-11-12T02:00:00", "2026-11-12T04:00:00"),
        _change("c2", "api", "2026-11-12T04:00:00", "2026-11-12T06:00:00"),
    ]
    assert find_collisions(changes) == []


def test_collision_same_service_overlap():
    changes = [
        _change("c1", "api", "2026-11-12T02:00:00", "2026-11-12T04:00:00"),
        _change("c2", "api", "2026-11-12T03:00:00", "2026-11-12T05:00:00"),
    ]
    collisions = find_collisions(changes)
    assert len(collisions) == 1
    assert collisions[0].first.id == "c1"
    assert collisions[0].second.id == "c2"


def test_collision_contained_window():
    changes = [
        _change("c1", "api", "2026-11-12T02:00:00", "2026-11-12T06:00:00"),
        _change("c2", "api", "2026-11-12T03:00:00", "2026-11-12T04:00:00"),
    ]
    assert len(find_collisions(changes)) == 1


def test_touching_windows_do_not_collide():
    changes = [
        _change("c1", "api", "2026-11-12T02:00:00", "2026-11-12T04:00:00"),
        _change("c2", "api", "2026-11-12T04:00:00", "2026-11-12T06:00:00"),
    ]
    assert find_collisions(changes) == []


def test_bad_dates_do_not_collide():
    changes = [
        _change("c1", "api", "soon", "2026-11-12T04:00:00"),
        _change("c2", "api", "2026-11-12T03:00:00", "2026-11-12T05:00:00"),
    ]
    assert find_collisions(changes) == []


def test_multiple_collisions():
    changes = [
        _change("c1", "api", "2026-11-12T02:00:00", "2026-11-12T05:00:00"),
        _change("c2", "api", "2026-11-12T03:00:00", "2026-11-12T04:00:00"),
        _change("c3", "api", "2026-11-12T04:30:00", "2026-11-12T06:00:00"),
    ]
    assert len(find_collisions(changes)) == 2


def test_markdown_clean():
    md = to_markdown([_change("c1", "api", "2026-11-12T02:00:00", "2026-11-12T04:00:00")], [])
    assert "Changes checked: 1" in md
    assert "Collisions found: 0" in md
    assert "No collisions" in md


def test_markdown_collision_table():
    changes = [
        _change("c1", "api", "2026-11-12T02:00:00", "2026-11-12T04:00:00"),
        _change("c2", "api", "2026-11-12T03:00:00", "2026-11-12T05:00:00"),
    ]
    md = to_markdown(changes, find_collisions(changes))
    assert "Collisions found: 1" in md
    assert "| api | c1 | c2 | 2026-11-12T02:00:00–2026-11-12T04:00:00 | 2026-11-12T03:00:00–2026-11-12T05:00:00 |" in md


def test_changes_from_json_defaults():
    changes = changes_from_json([{"id": "c1", "service": "api"}])
    assert changes[0].start == ""
    assert changes[0].owner == ""
