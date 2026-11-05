import pytest

from sre_toolkit.canary import CanaryAnalysis


def _analysis(**kwargs) -> CanaryAnalysis:
    defaults = dict(
        canary_error_rate=0.011, baseline_error_rate=0.010,
        canary_p99_ms=220, baseline_p99_ms=200, canary_requests=500,
    )
    defaults.update(kwargs)
    return CanaryAnalysis(**defaults)


def test_promote_when_within_thresholds():
    analysis = _analysis()
    assert analysis.verdict() == "promote"
    assert analysis.reasons() == ["within thresholds"]


def test_rollback_on_error_delta():
    analysis = _analysis(canary_error_rate=0.03)
    assert analysis.verdict() == "rollback"
    assert "error rate up 2.00 points" in analysis.reasons()[0]


def test_rollback_on_p99_ratio():
    analysis = _analysis(canary_p99_ms=400)
    assert analysis.verdict() == "rollback"
    assert "p99 2.00x baseline" in analysis.reasons()[0]


def test_hold_on_too_few_requests():
    analysis = _analysis(canary_requests=50)
    assert analysis.verdict() == "hold"
    assert "only 50 requests" in analysis.reasons()[0]


def test_hold_beats_rollback():
    analysis = _analysis(canary_requests=50, canary_error_rate=0.05)
    assert analysis.verdict() == "hold"


def test_exactly_at_threshold_promotes():
    analysis = _analysis(canary_error_rate=0.02)  # delta exactly 0.01
    assert analysis.verdict() == "promote"


def test_error_delta_math():
    assert _analysis().error_delta() == pytest.approx(0.001)


def test_p99_ratio_none_for_zero_baseline():
    analysis = _analysis(baseline_p99_ms=0)
    assert analysis.p99_ratio() is None
    assert analysis.verdict() == "promote"


def test_markdown_shows_verdict_and_metrics():
    md = _analysis(canary_error_rate=0.03).to_markdown()
    assert "# Canary analysis" in md
    assert "## Verdict: ROLLBACK" in md
    assert "delta +2.00 points" in md
    assert "p99 latency: canary 220ms vs baseline 200ms (1.10x)" in md
