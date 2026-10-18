from datetime import datetime

import pytest

from sre_toolkit.deploy import (
    DeployGate,
    FreezeWindow,
    WeeklyFreeze,
    deploy_gate_from_dict,
)


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def test_explicit_window_contains():
    window = FreezeWindow(
        name="diwali", start=_dt("2026-10-18T00:00"), end=_dt("2026-10-20T00:00")
    )
    assert window.contains(_dt("2026-10-19T12:00")) is True
    assert window.contains(_dt("2026-10-17T23:59")) is False
    assert window.contains(_dt("2026-10-20T00:01")) is False


def test_explicit_window_start_inclusive_end_exclusive():
    window = FreezeWindow(
        name="x", start=_dt("2026-10-18T00:00"), end=_dt("2026-10-20T00:00")
    )
    assert window.contains(_dt("2026-10-18T00:00")) is True
    assert window.contains(_dt("2026-10-20T00:00")) is False


def test_weekly_freeze_inside_window():
    # No weekend deploys: Friday 18:00 -> Monday 09:00.
    freeze = WeeklyFreeze(
        name="weekend",
        weekday=4,
        start_time=_dt("2026-01-01T18:00").time(),
        end_weekday=0,
        end_time=_dt("2026-01-01T09:00").time(),
    )
    assert freeze.contains(_dt("2026-10-17T10:00")) is True  # Saturday
    assert freeze.contains(_dt("2026-10-19T08:59")) is True  # Monday morning
    assert freeze.contains(_dt("2026-10-16T18:30")) is True  # Friday evening


def test_weekly_freeze_outside_window():
    freeze = WeeklyFreeze(
        name="weekend",
        weekday=4,
        start_time=_dt("2026-01-01T18:00").time(),
        end_weekday=0,
        end_time=_dt("2026-01-01T09:00").time(),
    )
    assert freeze.contains(_dt("2026-10-16T17:59")) is False  # Friday, pre-freeze
    assert freeze.contains(_dt("2026-10-19T09:00")) is False  # Monday, freeze over
    assert freeze.contains(_dt("2026-10-14T12:00")) is False  # Wednesday


def test_weekly_freeze_same_day_overnight():
    # Nightly freeze 22:00 -> 06:00.
    freeze = WeeklyFreeze(
        name="nightly",
        weekday=2,
        start_time=_dt("2026-01-01T22:00").time(),
        end_weekday=2,
        end_time=_dt("2026-01-01T06:00").time(),
    )
    assert freeze.contains(_dt("2026-10-14T23:00")) is True  # Wednesday night
    assert freeze.contains(_dt("2026-10-15T05:00")) is True  # Thursday early
    assert freeze.contains(_dt("2026-10-14T12:00")) is False


def test_gate_allowed_with_no_freezes():
    gate = DeployGate()
    result = gate.check(_dt("2026-10-18T12:00"))
    assert result.allowed is True
    assert result.blocking is None


def test_gate_blocked_names_window():
    gate = DeployGate(
        freezes=[
            FreezeWindow(
                name="diwali",
                start=_dt("2026-10-18T00:00"),
                end=_dt("2026-10-20T00:00"),
                reason="festival blackout",
            )
        ]
    )
    result = gate.check(_dt("2026-10-19T12:00"))
    assert result.allowed is False
    assert result.blocking is not None
    assert result.blocking.name == "diwali"


def test_gate_first_blocking_window_wins():
    gate = DeployGate(
        freezes=[
            FreezeWindow(name="a", start=_dt("2026-10-19T00:00"), end=_dt("2026-10-19T12:00")),
            FreezeWindow(name="b", start=_dt("2026-10-19T06:00"), end=_dt("2026-10-19T18:00")),
        ]
    )
    result = gate.check(_dt("2026-10-19T08:00"))
    assert result.allowed is False
    assert result.blocking.name == "a"


def test_gate_markdown_blocked():
    gate = DeployGate(
        freezes=[
            FreezeWindow(
                name="diwali",
                start=_dt("2026-10-18T00:00"),
                end=_dt("2026-10-20T00:00"),
                reason="festival blackout",
            )
        ]
    )
    md = gate.check(_dt("2026-10-19T12:00")).to_markdown()
    assert "BLOCKED" in md
    assert "diwali" in md
    assert "festival blackout" in md


def test_gate_markdown_allowed():
    md = DeployGate().check(_dt("2026-10-18T12:00")).to_markdown()
    assert "ALLOWED" in md


def test_from_dict_explicit_and_weekly():
    gate = deploy_gate_from_dict(
        {
            "freezes": [
                {
                    "kind": "explicit",
                    "name": "diwali",
                    "start": "2026-10-18T00:00",
                    "end": "2026-10-20T00:00",
                },
                {
                    "kind": "weekly",
                    "name": "weekend",
                    "weekday": 4,
                    "start_time": "18:00",
                    "end_weekday": 0,
                    "end_time": "09:00",
                },
            ]
        }
    )
    assert len(gate.freezes) == 2
    assert isinstance(gate.freezes[0], FreezeWindow)
    assert isinstance(gate.freezes[1], WeeklyFreeze)
    # Saturday is inside the weekend freeze.
    assert gate.check(_dt("2026-10-17T10:00")).allowed is False
    # Wednesday midday, outside diwali: allowed.
    assert gate.check(_dt("2026-10-14T12:00")).allowed is True


def test_from_dict_ignores_unknown_keys():
    gate = deploy_gate_from_dict({"freezes": [], "bogus": True})
    assert gate.freezes == []


def test_from_dict_bad_datetime_raises():
    with pytest.raises(ValueError):
        deploy_gate_from_dict(
            {"freezes": [{"name": "x", "start": "not-a-date", "end": "2026-10-20T00:00"}]}
        )
