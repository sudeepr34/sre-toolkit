from sre_toolkit.log_triage import error_rate, parse_line, summarize

SAMPLE = [
    "2026-10-04 10:15:01 INFO server started on :8080",
    "2026-10-04 10:15:22 ERROR connection refused: postgres-primary:5432",
    "2026-10-04 10:15:23 ERROR connection refused: postgres-primary:5432",
    "2026-10-04 10:15:40 WARN upstream timeout after 30s: /api/checkout",
    "2026-10-04 10:16:02 CRITICAL out of memory: killing process",
    "not a log line at all",
]


def test_parse_line_extracts_level_and_message():
    entry = parse_line("2026-10-04 10:15:22 ERROR connection refused")
    assert entry == {"level": "ERROR", "message": "connection refused"}


def test_parse_line_returns_none_for_garbage():
    assert parse_line("hello world") is None


def test_warn_normalized_to_warning():
    assert parse_line("2026-10-04 10:15:40 WARN slow query")["level"] == "WARNING"


def test_summarize_counts_and_top_errors():
    summary = summarize(SAMPLE, top_n=5)
    assert summary.total == 6
    assert summary.parsed == 5
    assert summary.by_level["ERROR"] == 2
    assert summary.top_errors[0] == ("connection refused: postgres-primary:5432", 2)


def test_error_rate():
    summary = summarize(SAMPLE)
    assert error_rate(summary) == 3 / 5


def test_error_rate_empty():
    assert error_rate(summarize([])) == 0.0
