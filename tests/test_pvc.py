import pytest

from sre_toolkit.pvc import (
    check_volumes,
    volumes_from_json,
    to_markdown,
    Volume,
)


def _volume(**kwargs) -> Volume:
    defaults = dict(name="data-pvc", namespace="prod", capacity_gi=100.0, used_gi=40.0)
    defaults.update(kwargs)
    return Volume(**defaults)


def test_ok_volume():
    results = check_volumes([_volume()])
    assert results[0].status == "ok"
    assert results[0].used_pct == pytest.approx(40.0)


def test_warning_volume():
    results = check_volumes([_volume(used_gi=85.0)])
    assert results[0].status == "warning"


def test_critical_volume():
    results = check_volumes([_volume(used_gi=97.0)])
    assert results[0].status == "critical"


def test_boundary_at_warning_is_warning():
    results = check_volumes([_volume(used_gi=80.0)])
    assert results[0].status == "warning"


def test_boundary_at_critical_is_critical():
    results = check_volumes([_volume(used_gi=95.0)])
    assert results[0].status == "critical"


def test_zero_capacity_unknown_pct_ok():
    results = check_volumes([_volume(capacity_gi=0.0)])
    assert results[0].used_pct is None
    assert results[0].status == "ok"


def test_custom_thresholds():
    results = check_volumes(
        [_volume(used_gi=60.0)], warning_pct=50.0, critical_pct=90.0
    )
    assert results[0].status == "warning"


def test_markdown_sorted_fullest_first():
    volumes = [
        _volume(name="small", used_gi=10.0),
        _volume(name="full", used_gi=97.0),
        _volume(name="half", used_gi=50.0),
    ]
    md = to_markdown(check_volumes(volumes))
    assert "Volumes checked: 3" in md
    assert "- Critical: 1" in md
    assert "- Warning: 0" in md
    assert "- OK: 2" in md
    assert md.index("full") < md.index("half") < md.index("small")
    assert "| full | prod | 100 | 97 | 97.0 | critical |" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "Volumes checked: 0" in md
    assert "No volumes to check." in md


def test_volumes_from_json_defaults():
    volumes = volumes_from_json([{"name": "x"}])
    assert volumes[0].namespace == "default"
    assert volumes[0].capacity_gi == 0.0
