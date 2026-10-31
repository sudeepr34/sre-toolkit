import pytest

from sre_toolkit.dependency import ServiceGraph, graph_from_json


def _graph() -> ServiceGraph:
    return ServiceGraph({
        "api": ["db", "cache"],
        "web": ["api"],
        "worker": ["db", "queue"],
        "db": [],
        "cache": ["db"],
        "queue": [],
    })


def test_direct_dependencies():
    assert _graph().dependencies("api") == ["cache", "db"]


def test_direct_dependents():
    assert _graph().dependents("db") == ["api", "cache", "worker"]


def test_transitive_dependencies():
    assert _graph().transitive_dependencies("web") == ["api", "cache", "db"]


def test_transitive_dependencies_leaf():
    assert _graph().transitive_dependencies("db") == []


def test_blast_radius():
    # db failing breaks api, cache, worker directly, and web via api
    assert _graph().blast_radius("db") == ["api", "cache", "web", "worker"]


def test_blast_radius_leaf():
    assert _graph().blast_radius("web") == []


def test_unknown_service_raises():
    with pytest.raises(ValueError) as excinfo:
        _graph().dependencies("nope")
    assert "api" in str(excinfo.value)


def test_no_cycles():
    assert _graph().find_cycles() == []


def test_cycle_detected():
    graph = ServiceGraph({"a": ["b"], "b": ["c"], "c": ["a"]})
    cycles = graph.find_cycles()
    assert len(cycles) == 1
    assert cycles[0] == ["a", "b", "c", "a"]


def test_self_loop_is_a_cycle():
    graph = ServiceGraph({"a": ["a"]})
    assert graph.find_cycles() == [["a", "a"]]


def test_dep_only_node_appears():
    graph = ServiceGraph({"api": ["db"]})
    assert graph.services() == ["api", "db"]
    assert graph.dependencies("db") == []


def test_service_markdown():
    md = _graph().service_markdown("db")
    assert "# Dependency report: db" in md
    assert "Direct dependents (3): api, cache, worker" in md
    assert "## Blast radius (4 services)" in md
    assert "- web" in md


def test_full_markdown_table_and_no_cycles():
    md = _graph().full_markdown()
    assert "| db | 0 | 3 | 4 |" in md
    assert "No dependency cycles." in md


def test_full_markdown_lists_cycles():
    graph = ServiceGraph({"a": ["b"], "b": ["a"]})
    md = graph.full_markdown()
    assert "## Cycles detected" in md
    assert "a -> b -> a" in md


def test_graph_from_json():
    graph = graph_from_json({"api": ["db"], "db": []})
    assert graph.blast_radius("db") == ["api"]
