from sre_toolkit.limitrange import (
    check_limit_ranges,
    limit_ranges_from_json,
    to_markdown,
    LimitRange,
)


def _lr(**kwargs) -> LimitRange:
    defaults = dict(
        name="limits",
        namespace="prod",
        has_default_cpu=True,
        has_default_memory=True,
        has_max_cpu=True,
        has_max_memory=True,
        owner="platform",
    )
    defaults.update(kwargs)
    return LimitRange(**defaults)


def test_clean_ok():
    results = check_limit_ranges([_lr()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_no_default_cpu_blocked():
    results = check_limit_ranges([_lr(has_default_cpu=False)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no default cpu"]


def test_no_default_memory_blocked():
    results = check_limit_ranges([_lr(has_default_memory=False)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no default memory"]


def test_no_max_cpu_risky():
    results = check_limit_ranges([_lr(has_max_cpu=False)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no max cpu"]


def test_no_max_memory_risky():
    results = check_limit_ranges([_lr(has_max_memory=False)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no max memory"]


def test_missing_owner_risky():
    results = check_limit_ranges([_lr(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_blocked_beats_risky():
    results = check_limit_ranges(
        [_lr(has_default_cpu=False, has_max_cpu=False, owner="")]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == [
        "no default cpu",
        "no max cpu",
        "no owner",
    ]


def test_both_defaults_missing():
    results = check_limit_ranges(
        [_lr(has_default_cpu=False, has_default_memory=False)]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no default cpu", "no default memory"]


def test_markdown_counts_and_sorted():
    ranges = [
        _lr(name="wide", has_default_cpu=False),
        _lr(),
    ]
    md = to_markdown(check_limit_ranges(ranges))
    assert "LimitRanges checked: 2" in md
    assert "Blocked: 1" in md
    assert "OK: 1" in md
    assert md.index("limits") < md.index("wide")
    assert (
        "| wide | prod | no | yes | yes | yes | platform | blocked |"
        " no default cpu |" in md
    )
    assert "| limits | prod | yes | yes | yes | yes | platform | ok | — |" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "LimitRanges checked: 0" in md
    assert "No LimitRanges to check." in md


def test_limit_ranges_from_json_defaults():
    ranges = limit_ranges_from_json([{"name": "x"}])
    assert ranges[0].namespace == "default"
    assert ranges[0].has_default_cpu is False
    assert ranges[0].has_default_memory is False
    assert ranges[0].has_max_cpu is False
    assert ranges[0].has_max_memory is False
    assert ranges[0].owner == ""
