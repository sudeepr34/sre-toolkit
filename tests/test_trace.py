from sre_toolkit.trace import (
    critical_path,
    error_spans,
    slowest_span,
    spans_from_json,
    to_markdown,
    total_duration_ms,
    Span,
)


def _spans() -> list:
    # root (0-100) -> api (10-90) -> db (20-80) and cache (20-30, error)
    return [
        Span("t1", "r", "", "edge", "handle", 0, 100),
        Span("t1", "a", "r", "api", "process", 10, 80),
        Span("t1", "d", "a", "db", "query", 20, 60),
        Span("t1", "c", "a", "cache", "get", 20, 10, "error"),
    ]


def test_total_duration():
    assert total_duration_ms(_spans()) == 100


def test_total_duration_empty():
    assert total_duration_ms([]) == 0.0


def test_slowest_span():
    slowest = slowest_span(_spans())
    assert slowest is not None
    assert slowest.span_id == "r"
    assert slowest.duration_ms == 100


def test_slowest_span_empty_is_none():
    assert slowest_span([]) is None


def test_error_spans():
    errors = error_spans(_spans())
    assert [s.span_id for s in errors] == ["c"]


def test_critical_path_follows_longest_chain():
    path = critical_path(_spans())
    assert [s.span_id for s in path] == ["r", "a", "d"]
    assert sum(s.duration_ms for s in path) == 240


def test_critical_path_empty():
    assert critical_path([]) == []


def test_critical_path_single_span():
    path = critical_path([Span("t1", "r", "", "edge", "handle", 0, 5)])
    assert [s.span_id for s in path] == ["r"]


def test_markdown_sections():
    md = to_markdown(_spans())
    assert "Spans: 4" in md
    assert "Total duration: 100.0 ms" in md
    assert "Error spans: 1" in md
    assert "Slowest span: edge::handle (100.0 ms)" in md
    assert "Critical path: 240.0 ms" in md
    assert "- db::query (60.0 ms)" in md
    assert "- cache::get (c)" in md


def test_spans_from_json_defaults():
    spans = spans_from_json([{"trace_id": "t", "span_id": "s"}])
    assert spans[0].parent_id == ""
    assert spans[0].service == "unnamed"
    assert spans[0].status == "ok"
