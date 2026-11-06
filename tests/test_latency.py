import pytest

from sre_toolkit.latency import analyze, breached, percentile, to_markdown


def test_percentile_nearest_rank():
    samples = sorted(range(1, 101))  # 1..100
    assert percentile(samples, 50) == 50
    assert percentile(samples, 95) == 95
    assert percentile(samples, 99) == 99
    assert percentile(samples, 100) == 100


def test_percentile_single_sample():
    assert percentile([42.0], 95) == 42.0


def test_percentile_empty_raises():
    with pytest.raises(ValueError, match="no samples"):
        percentile([], 95)


def test_analyze_summary():
    stats = analyze([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
    assert stats.count == 10
    assert stats.minimum == 10
    assert stats.maximum == 100
    assert stats.mean == pytest.approx(55.0)
    assert stats.p50 == 50
    assert stats.p95 == 100
    assert stats.p99 == 100


def test_analyze_sorts_input():
    stats = analyze([100, 10, 50])
    assert stats.minimum == 10
    assert stats.maximum == 100
    assert stats.p50 == 50


def test_analyze_empty_raises():
    with pytest.raises(ValueError, match="no samples"):
        analyze([])


def test_breached_above_threshold():
    stats = analyze([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
    assert breached(stats, 99) is True


def test_not_breached_at_threshold():
    stats = analyze([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
    assert breached(stats, 100) is False


def test_markdown_breach():
    stats = analyze([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
    md = to_markdown(stats, 90)
    assert "Samples: 10" in md
    assert "| p95 | 100.0 |" in md
    assert "BREACH" in md


def test_markdown_within_threshold():
    stats = analyze([10, 20, 30])
    md = to_markdown(stats, 500)
    assert "within threshold" in md
