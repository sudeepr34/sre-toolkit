import pytest

from sre_toolkit.quota import (
    check_quotas,
    namespaces_from_json,
    to_markdown,
    Namespace,
)


def _namespace(**kwargs) -> Namespace:
    defaults = dict(
        name="prod", cpu_limit=10.0, cpu_used=5.0,
        memory_limit=64.0, memory_used=32.0,
    )
    defaults.update(kwargs)
    return Namespace(**defaults)


def test_under_threshold_clean():
    results = check_quotas([_namespace()])
    assert results[0].issues == []
    assert results[0].cpu_pct == pytest.approx(50.0)
    assert results[0].memory_pct == pytest.approx(50.0)


def test_cpu_at_threshold_flagged():
    results = check_quotas([_namespace(cpu_used=9.0)])
    assert results[0].issues == ["cpu at 90.0%"]


def test_memory_over_threshold_flagged():
    results = check_quotas([_namespace(memory_used=60.0)])
    assert results[0].issues == ["memory at 93.8%"]


def test_both_flagged():
    results = check_quotas([_namespace(cpu_used=9.5, memory_used=62.0)])
    assert results[0].issues == ["cpu at 95.0%", "memory at 96.9%"]


def test_unset_limit_unknown_pct():
    results = check_quotas([_namespace(cpu_limit=0.0, memory_limit=0.0)])
    assert results[0].cpu_pct is None
    assert results[0].memory_pct is None
    assert results[0].issues == []


def test_custom_threshold():
    results = check_quotas([_namespace(cpu_used=6.0)], threshold_pct=50.0)
    assert results[0].issues == ["cpu at 60.0%", "memory at 50.0%"]


def test_markdown_sorted_by_name():
    namespaces = [
        _namespace(name="staging", cpu_used=9.0),
        _namespace(name="prod"),
    ]
    md = to_markdown(check_quotas(namespaces))
    assert "Namespaces checked: 2" in md
    assert "Namespaces over threshold: 1" in md
    assert md.index("prod") < md.index("staging")
    assert "| staging | 90.0 | 50.0 | cpu at 90.0% |" in md
    assert "| prod | 50.0 | 50.0 | — |" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "Namespaces checked: 0" in md
    assert "No namespaces to check." in md


def test_namespaces_from_json_defaults():
    namespaces = namespaces_from_json([{"name": "x"}])
    assert namespaces[0].cpu_limit == 0.0
    assert namespaces[0].memory_used == 0.0
