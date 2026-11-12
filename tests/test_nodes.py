import pytest

from sre_toolkit.nodes import (
    check_nodes,
    nodes_from_json,
    to_markdown,
    Node,
)


def _node(**kwargs) -> Node:
    defaults = dict(
        name="node-1", status="ready",
        cpu_capacity=8.0, cpu_requested=4.0,
        memory_capacity=32.0, memory_requested=16.0,
    )
    defaults.update(kwargs)
    return Node(**defaults)


def test_ready_node_clean():
    results = check_nodes([_node()])
    assert results[0].issues == []
    assert results[0].cpu_pct == pytest.approx(50.0)
    assert results[0].memory_pct == pytest.approx(50.0)


def test_not_ready_node():
    results = check_nodes([_node(status="notready")])
    assert results[0].issues == ["not ready"]


def test_cpu_over_committed():
    results = check_nodes([_node(cpu_requested=9.0)])
    assert results[0].issues == ["cpu over-committed"]
    assert results[0].cpu_pct == pytest.approx(112.5)


def test_memory_over_committed():
    results = check_nodes([_node(memory_requested=40.0)])
    assert results[0].issues == ["memory over-committed"]


def test_exactly_at_threshold_is_clean():
    results = check_nodes([_node(cpu_requested=8.0, memory_requested=32.0)])
    assert results[0].issues == []


def test_custom_threshold():
    results = check_nodes([_node(cpu_requested=7.0)], overcommit_pct=80.0)
    assert results[0].issues == ["cpu over-committed"]


def test_zero_capacity_unknown_pct():
    results = check_nodes([_node(cpu_capacity=0.0, memory_capacity=0.0)])
    assert results[0].cpu_pct is None
    assert results[0].memory_pct is None
    assert results[0].issues == []


def test_multiple_issues_collected():
    results = check_nodes(
        [_node(status="notready", cpu_requested=9.0, memory_requested=40.0)]
    )
    assert results[0].issues == [
        "not ready", "cpu over-committed", "memory over-committed",
    ]


def test_markdown_sorted_by_name():
    nodes = [
        _node(name="node-b", status="notready"),
        _node(name="node-a"),
    ]
    md = to_markdown(check_nodes(nodes))
    assert "Nodes checked: 2" in md
    assert "Nodes with issues: 1" in md
    assert md.index("node-a") < md.index("node-b")
    assert "| node-b | notready | 50.0 | 50.0 | not ready |" in md
    assert "| node-a | ready | 50.0 | 50.0 | — |" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "Nodes checked: 0" in md
    assert "No nodes to check." in md


def test_nodes_from_json_defaults():
    nodes = nodes_from_json([{"name": "x"}])
    assert nodes[0].status == "ready"
    assert nodes[0].cpu_capacity == 0.0
