import pytest

from sre_toolkit.capacity import CapacityPlan


def _plan(**kwargs) -> CapacityPlan:
    defaults = dict(current_load=800, capacity=1000, growth_rate=0.05)
    defaults.update(kwargs)
    return CapacityPlan(**defaults)


def test_projected_load_compounds():
    plan = _plan()
    assert plan.projected_load(0) == 800
    assert plan.projected_load(1) == pytest.approx(840)
    assert plan.projected_load(2) == pytest.approx(882)


def test_projected_load_negative_period_rejected():
    with pytest.raises(ValueError):
        _plan().projected_load(-1)


def test_utilization():
    plan = _plan()
    assert plan.utilization(0) == pytest.approx(0.8)
    assert plan.utilization(1) == pytest.approx(0.84)


def test_forecast_length():
    plan = _plan(periods=3)
    assert len(plan.forecast()) == 4  # periods 0..3 inclusive
    assert plan.forecast()[0][0] == 0


def test_breach_period():
    plan = _plan(current_load=600, capacity=1000, growth_rate=0.10)
    # 600, 660, 726 -> breach at period 2 (72.6% > 70%)
    assert plan.breach_period() == 2


def test_breach_period_none_when_flat():
    plan = _plan(current_load=500, capacity=1000, growth_rate=0.0)
    assert plan.breach_period() is None


def test_breach_period_zero_when_already_over():
    plan = _plan(current_load=900, capacity=1000, growth_rate=0.0)
    assert plan.breach_period() == 0


def test_capacity_needed():
    plan = _plan(current_load=600, capacity=1000, growth_rate=0.10)
    # load at period 2 is 726; 726 / 0.7 = 1037.14
    assert plan.capacity_needed(2) == pytest.approx(1037.142857, rel=1e-6)


def test_validation():
    with pytest.raises(ValueError):
        _plan(capacity=0)
    with pytest.raises(ValueError):
        _plan(current_load=-5)
    with pytest.raises(ValueError):
        _plan(target_utilization=0)
    with pytest.raises(ValueError):
        _plan(target_utilization=1.5)
    with pytest.raises(ValueError):
        _plan(periods=-1)


def test_markdown_table_and_recommendation():
    plan = _plan(current_load=600, capacity=1000, growth_rate=0.10, periods=3)
    md = plan.to_markdown()
    assert "# Capacity forecast" in md
    assert "| 2 | 726.0 rps | 72.6% | breach |" in md
    assert "crosses target at period 2" in md
    assert "1.04x current" in md


def test_markdown_no_breach_message():
    plan = _plan(current_load=500, capacity=1000, growth_rate=0.0, periods=2)
    md = plan.to_markdown()
    assert "stays under target for all 2 periods" in md
