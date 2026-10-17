import pytest

from sre_toolkit.slo import (
    SloAssessment,
    budget_consumed,
    burn_rate,
    severity_for_burn_rate,
    slo_assessment_from_dict,
    time_to_exhaustion_hours,
)


def test_burn_rate_at_five_times_budget():
    # 0.5% observed errors against a 99.9% SLO (0.1% budgeted).
    assert burn_rate(0.005, 0.999) == pytest.approx(5.0)


def test_burn_rate_exactly_at_budget_pace():
    assert burn_rate(0.01, 0.99) == pytest.approx(1.0)


def test_burn_rate_zero_errors():
    assert burn_rate(0.0, 0.999) == 0.0


def test_burn_rate_rejects_bad_target():
    with pytest.raises(ValueError):
        burn_rate(0.001, 1.0)
    with pytest.raises(ValueError):
        burn_rate(0.001, 0.0)


def test_burn_rate_rejects_negative_errors():
    with pytest.raises(ValueError):
        burn_rate(-0.001, 0.999)


def test_severity_page_boundary():
    assert severity_for_burn_rate(14.4) == "page"
    assert severity_for_burn_rate(30.0) == "page"
    assert severity_for_burn_rate(14.39) == "ticket"


def test_severity_ticket_boundary():
    assert severity_for_burn_rate(6.0) == "ticket"
    assert severity_for_burn_rate(5.99) == "watch"


def test_severity_watch_boundary():
    assert severity_for_burn_rate(1.0) == "watch"
    assert severity_for_burn_rate(0.99) == "healthy"
    assert severity_for_burn_rate(0.0) == "healthy"


def test_budget_consumed_full_window_at_budget_pace():
    # 1x burn for the whole 720h window consumes exactly the budget.
    assert budget_consumed(1.0, 720.0, 720.0) == pytest.approx(1.0)


def test_budget_consumed_can_exceed_total():
    # 2x burn for the whole window blows through 200% of the budget.
    assert budget_consumed(2.0, 720.0, 720.0) == pytest.approx(2.0)


def test_budget_consumed_partial_window():
    assert budget_consumed(6.0, 60.0, 720.0) == pytest.approx(0.5)


def test_budget_consumed_rejects_bad_window():
    with pytest.raises(ValueError):
        budget_consumed(1.0, 10.0, 0.0)
    with pytest.raises(ValueError):
        budget_consumed(1.0, 800.0, 720.0)


def test_time_to_exhaustion():
    # Half the budget left at 2x burn over a 720h window: 180h to go.
    assert time_to_exhaustion_hours(0.5, 2.0, 720.0) == pytest.approx(180.0)


def test_time_to_exhaustion_none_when_exhausted_or_idle():
    assert time_to_exhaustion_hours(0.0, 2.0, 720.0) is None
    assert time_to_exhaustion_hours(0.5, 0.0, 720.0) is None


def test_assessment_properties():
    a = SloAssessment(
        slo_target=0.999,
        observed_error_ratio=0.005,
        window_hours=720.0,
        elapsed_hours=720.0,
    )
    assert a.rate == pytest.approx(5.0)
    assert a.severity == "watch"
    assert a.consumed == pytest.approx(5.0)
    assert a.exhausted is True
    assert a.remaining == pytest.approx(0.0)
    assert a.exhaustion_hours is None


def test_assessment_healthy():
    a = SloAssessment(slo_target=0.999, observed_error_ratio=0.0005)
    assert a.rate == pytest.approx(0.5)
    assert a.severity == "healthy"
    assert a.exhausted is False
    assert a.remaining == pytest.approx(0.5)
    assert a.exhaustion_hours == pytest.approx(720.0)


def test_assessment_rejects_bad_input():
    with pytest.raises(ValueError):
        SloAssessment(slo_target=1.5)
    with pytest.raises(ValueError):
        SloAssessment(elapsed_hours=800.0, window_hours=720.0)


def test_from_dict_defaults_and_unknown_keys():
    a = slo_assessment_from_dict({"observed_error_ratio": 0.002, "bogus": 1})
    assert a.slo_target == pytest.approx(0.999)
    assert a.observed_error_ratio == pytest.approx(0.002)
    assert a.window_hours == pytest.approx(720.0)
    assert a.elapsed_hours == pytest.approx(720.0)


def test_from_dict_elapsed_defaults_to_window():
    a = slo_assessment_from_dict({"window_hours": 168.0})
    assert a.elapsed_hours == pytest.approx(168.0)


def test_markdown_shows_key_fields():
    a = SloAssessment(slo_target=0.999, observed_error_ratio=0.005)
    md = a.to_markdown()
    assert "# SLO burn-rate assessment" in md
    assert "Burn rate: 5.00x" in md
    assert "Severity: **watch**" in md
    assert "— EXHAUSTED" in md
    assert "Recommendation:" in md


def test_markdown_healthy_shows_exhaustion_time():
    a = SloAssessment(slo_target=0.999, observed_error_ratio=0.0005)
    md = a.to_markdown()
    assert "Severity: **healthy**" in md
    assert "EXHAUSTED" not in md
    assert "Time to exhaustion at current burn: 720.0h" in md
