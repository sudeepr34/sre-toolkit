from datetime import date

import pytest

from sre_toolkit.oncall import Rotation, rotation_from_dict

ROTA_DATA = {
    "name": "backend",
    "members": ["priya", "sudeep", "arjun"],
    "start_date": "2026-10-05",
    "shift_days": 7,
}


def _rota(**overrides):
    data = dict(ROTA_DATA)
    data.update(overrides)
    return rotation_from_dict(data)


def test_first_member_on_start_date():
    rota = _rota()
    assert rota.who_is_on(date(2026, 10, 5)) == "priya"


def test_rotation_advances_weekly():
    rota = _rota()
    assert rota.who_is_on(date(2026, 10, 11)) == "priya"  # last day of shift 1
    assert rota.who_is_on(date(2026, 10, 12)) == "sudeep"  # handoff day
    assert rota.who_is_on(date(2026, 10, 19)) == "arjun"
    assert rota.who_is_on(date(2026, 10, 26)) == "priya"  # wraps around


def test_shift_window():
    rota = _rota()
    start, end = rota.shift_window(date(2026, 10, 14))
    assert start == date(2026, 10, 12)
    assert end == date(2026, 10, 19)


def test_upcoming_lists_next_shifts():
    rota = _rota()
    upcoming = rota.upcoming(date(2026, 10, 14), 3)
    assert upcoming == [
        ("sudeep", date(2026, 10, 12)),
        ("arjun", date(2026, 10, 19)),
        ("priya", date(2026, 10, 26)),
    ]


def test_upcoming_zero_count():
    assert _rota().upcoming(date(2026, 10, 14), 0) == []


def test_upcoming_rejects_negative_count():
    with pytest.raises(ValueError):
        _rota().upcoming(date(2026, 10, 14), -1)


def test_date_before_rotation_start_raises():
    rota = _rota()
    with pytest.raises(ValueError):
        rota.who_is_on(date(2026, 10, 4))
    with pytest.raises(ValueError):
        rota.shift_window(date(2026, 10, 4))


def test_rotation_needs_members():
    with pytest.raises(ValueError):
        rotation_from_dict({"name": "empty", "members": []})


def test_rotation_rejects_bad_shift_days():
    with pytest.raises(ValueError):
        rotation_from_dict({**ROTA_DATA, "shift_days": 0})


def test_from_dict_rejects_bad_date():
    with pytest.raises(ValueError):
        rotation_from_dict({**ROTA_DATA, "start_date": "yesterday"})


def test_from_dict_defaults():
    rota = rotation_from_dict({"members": ["solo"]})
    assert rota.name == "rotation"
    assert rota.shift_days == 7
    assert rota.start_date == date.today()


def test_from_dict_ignores_unknown_keys():
    rota = rotation_from_dict({**ROTA_DATA, "bogus": True})
    assert rota.name == "backend"


def test_markdown_shows_who_is_on():
    md = _rota().to_markdown(date(2026, 10, 14))
    assert "# On-call: backend" in md
    assert "On call now: **sudeep**" in md
    assert "2026-10-12 -> 2026-10-19" in md
    assert "## Up next" in md
    assert "2026-10-19: arjun" in md
    assert "2026-10-26: priya" in md
