from datetime import datetime

from sre_toolkit.events import (
    events_from_json,
    find_bursts,
    find_correlated,
    to_markdown,
    Event,
)


def _event(service: str, timestamp: str) -> Event:
    return Event(service, timestamp, "error", "something failed")


def test_burst_found():
    events = [_event("api", f"2026-11-10T10:{minute:02d}:00") for minute in range(5)]
    bursts = find_bursts(events, window_minutes=15, threshold=5)
    assert len(bursts) == 1
    assert bursts[0].service == "api"
    assert bursts[0].count == 5
    assert bursts[0].window_start == datetime(2026, 11, 10, 10, 0)


def test_no_burst_below_threshold():
    events = [_event("api", f"2026-11-10T10:{minute:02d}:00") for minute in range(4)]
    assert find_bursts(events, window_minutes=15, threshold=5) == []


def test_no_burst_when_spread_out():
    events = [_event("api", f"2026-11-10T{hour:02d}:00:00") for hour in range(10, 15)]
    assert find_bursts(events, window_minutes=15, threshold=5) == []


def test_two_bursts_same_service():
    events = [
        _event("api", f"2026-11-10T10:{minute:02d}:00") for minute in range(5)
    ] + [
        _event("api", f"2026-11-10T11:{minute:02d}:00") for minute in range(5)
    ]
    bursts = find_bursts(events, window_minutes=15, threshold=5)
    assert len(bursts) == 2
    assert bursts[0].count == 5 and bursts[1].count == 5


def test_correlated_two_services_same_window():
    events = [
        _event("api", "2026-11-10T10:02:00"),
        _event("db", "2026-11-10T10:05:00"),
        _event("cache", "2026-11-10T10:12:00"),
    ]
    groups = find_correlated(events, window_minutes=15)
    assert len(groups) == 1
    assert groups[0].services == ["api", "cache", "db"]
    assert groups[0].window_start == datetime(2026, 11, 10, 10, 0)


def test_not_correlated_different_windows():
    events = [
        _event("api", "2026-11-10T10:02:00"),
        _event("db", "2026-11-10T10:20:00"),
    ]
    assert find_correlated(events, window_minutes=15) == []


def test_bad_timestamps_ignored():
    events = [_event("api", "soon"), _event("api", "2026-11-10T10:00:00")]
    assert find_bursts(events) == []
    assert find_correlated(events) == []


def test_markdown_sections():
    events = [
        _event("api", f"2026-11-10T10:{minute:02d}:00") for minute in range(5)
    ] + [_event("db", "2026-11-10T10:05:00")]
    bursts = find_bursts(events)
    correlated = find_correlated(events)
    md = to_markdown(bursts, correlated, 15)
    assert "Window: 15 minutes" in md
    assert "- Bursts found: 1" in md
    assert "- Correlated windows: 1" in md
    assert "| api | 2026-11-10T10:00:00 | 5 |" in md
    assert "| 2026-11-10T10:00:00 | api, db |" in md


def test_markdown_empty():
    md = to_markdown([], [], 15)
    assert "No bursts or correlated windows found." in md


def test_events_from_json_defaults():
    events = events_from_json([{"service": "x", "timestamp": "2026-11-10T10:00:00"}])
    assert events[0].severity == "info"
    assert events[0].message == ""
