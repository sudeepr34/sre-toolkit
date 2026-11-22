from sre_toolkit.priority import (
    check_priority_classes,
    priority_classes_from_json,
    to_markdown,
    PriorityClass,
)


def _pc(**kwargs) -> PriorityClass:
    defaults = dict(
        name="high",
        value=1000000,
        global_default=False,
        owner="platform",
    )
    defaults.update(kwargs)
    return PriorityClass(**defaults)


def test_clean_ok():
    results = check_priority_classes([_pc()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_negative_value_blocked():
    results = check_priority_classes([_pc(value=-1)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["negative value"]


def test_value_over_max_risky():
    results = check_priority_classes([_pc(value=1000000001)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["value over maximum"]


def test_value_at_max_ok():
    results = check_priority_classes([_pc(value=1000000000)])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_duplicate_global_default_risky():
    results = check_priority_classes(
        [_pc(global_default=True), _pc(name="low", global_default=True)]
    )
    assert results[0].verdict == "risky"
    assert results[0].issues == ["duplicate global default"]
    assert results[1].verdict == "risky"
    assert results[1].issues == ["duplicate global default"]


def test_missing_owner_risky():
    results = check_priority_classes([_pc(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_blocked_beats_risky():
    results = check_priority_classes([_pc(value=-5, owner="")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["negative value", "no owner"]


def test_markdown_counts_and_sorted():
    classes = [
        _pc(name="low", value=-1),
        _pc(),
    ]
    md = to_markdown(check_priority_classes(classes))
    assert "PriorityClasses checked: 2" in md
    assert "Blocked: 1" in md
    assert "OK: 1" in md
    assert md.index("high") < md.index("low")
    assert "| low | -1 | no | platform | blocked | negative value |" in md
    assert "| high | 1000000 | no | platform | ok | — |" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "PriorityClasses checked: 0" in md
    assert "No PriorityClasses to check." in md


def test_priority_classes_from_json_defaults():
    classes = priority_classes_from_json([{"name": "x"}])
    assert classes[0].value == 0
    assert classes[0].global_default is False
    assert classes[0].owner == ""
