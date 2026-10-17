"""SLO burn-rate and error-budget math.

Implements the multi-window burn-rate alerting model from the Google SRE
workbook ("Alerting on SLOs"): the burn rate measures how fast the error
budget is being consumed relative to the sustainable pace, and the
severity tiers map directly to paging policy.

Tiers (burn rate = observed error ratio / budgeted error ratio):
  - >= 14.4 : page   -- fast burn, exhausts 2% of budget within an hour
  - >= 6    : ticket -- slow burn, exhausts 5% of budget within six hours
  - >= 1    : watch  -- consuming budget faster than the sustainable pace
  - < 1     : healthy
"""
from __future__ import annotations

from dataclasses import dataclass

PAGE_BURN_RATE = 14.4
TICKET_BURN_RATE = 6.0
WATCH_BURN_RATE = 1.0

_SEVERITY_ORDER = ("healthy", "watch", "ticket", "page")

_SEVERITY_BLURB = {
    "page": "fast burn: paging pace, 2% of budget gone within an hour",
    "ticket": "slow burn: ticket pace, 5% of budget gone within six hours",
    "watch": "elevated: consuming budget faster than the sustainable pace",
    "healthy": "within budget",
}

_RECOMMENDATION = {
    "page": "Page immediately and mitigate: at this pace the budget is gone within the hour.",
    "ticket": "Open a ticket and investigate today: slow-burn pace will page if it continues.",
    "watch": "Watch: over budget pace but not paging; review before it escalates.",
    "healthy": "Healthy: error rate is within the budgeted ratio. No action needed.",
}


def burn_rate(observed_error_ratio: float, slo_target: float) -> float:
    """How many times faster than sustainable the budget is being consumed.

    ``observed_error_ratio`` and ``slo_target`` are fractions: for a 99.9%
    SLO with 0.5% observed errors, pass 0.005 and 0.999 to get 5.0.
    """
    if not 0 < slo_target < 1:
        raise ValueError(f"slo_target must be between 0 and 1, got {slo_target}")
    if observed_error_ratio < 0:
        raise ValueError(
            f"observed_error_ratio must be >= 0, got {observed_error_ratio}"
        )
    return observed_error_ratio / (1 - slo_target)


def severity_for_burn_rate(rate: float) -> str:
    """Paging-policy severity for a burn rate: page, ticket, watch, healthy."""
    if rate >= PAGE_BURN_RATE:
        return "page"
    if rate >= TICKET_BURN_RATE:
        return "ticket"
    if rate >= WATCH_BURN_RATE:
        return "watch"
    return "healthy"


def budget_consumed(
    rate: float, elapsed_hours: float, window_hours: float
) -> float:
    """Fraction of the total error budget consumed so far (1.0 = exhausted)."""
    if window_hours <= 0:
        raise ValueError(f"window_hours must be > 0, got {window_hours}")
    if not 0 <= elapsed_hours <= window_hours:
        raise ValueError(
            f"elapsed_hours must be within [0, window_hours], got {elapsed_hours}"
        )
    return rate * elapsed_hours / window_hours


def time_to_exhaustion_hours(
    budget_remaining: float, rate: float, window_hours: float
) -> float | None:
    """Hours until the budget is exhausted at the current burn rate.

    None when the budget is already exhausted or the burn rate is zero
    (nothing is being consumed).
    """
    if budget_remaining <= 0 or rate <= 0:
        return None
    return budget_remaining / rate * window_hours


@dataclass
class SloAssessment:
    slo_target: float = 0.999
    observed_error_ratio: float = 0.0
    window_hours: float = 720.0
    elapsed_hours: float = 720.0

    def __post_init__(self) -> None:
        # Reuse the shared validators so bad input fails fast in one place.
        burn_rate(self.observed_error_ratio, self.slo_target)
        budget_consumed(1.0, self.elapsed_hours, self.window_hours)

    @property
    def rate(self) -> float:
        return burn_rate(self.observed_error_ratio, self.slo_target)

    @property
    def consumed(self) -> float:
        return budget_consumed(self.rate, self.elapsed_hours, self.window_hours)

    @property
    def remaining(self) -> float:
        return max(0.0, 1.0 - self.consumed)

    @property
    def severity(self) -> str:
        return severity_for_burn_rate(self.rate)

    @property
    def exhaustion_hours(self) -> float | None:
        return time_to_exhaustion_hours(self.remaining, self.rate, self.window_hours)

    @property
    def exhausted(self) -> bool:
        return self.consumed >= 1.0

    def to_markdown(self) -> str:
        lines = ["# SLO burn-rate assessment", ""]
        lines.append(
            f"- SLO target: {self.slo_target:.3%} | window: {self.window_hours:g}h "
            f"| elapsed: {self.elapsed_hours:g}h"
        )
        lines.append(
            f"- Observed error ratio: {self.observed_error_ratio:.3%} "
            f"(budgeted: {(1 - self.slo_target):.3%})"
        )
        lines.append(f"- Burn rate: {self.rate:.2f}x")
        consumed_pct = self.consumed * 100
        status = " — EXHAUSTED" if self.exhausted else ""
        lines.append(
            f"- Error budget consumed: {consumed_pct:.1f}%{status} "
            f"({self.remaining:.1%} remaining)"
        )
        lines.append(
            f"- Severity: **{self.severity}** ({_SEVERITY_BLURB[self.severity]})"
        )
        if self.exhausted:
            lines.append("- Time to exhaustion: already exhausted")
        elif self.exhaustion_hours is None:
            lines.append("- Time to exhaustion: n/a (no budget consumption)")
        else:
            lines.append(
                f"- Time to exhaustion at current burn: {self.exhaustion_hours:.1f}h"
            )
        lines.append(f"- Recommendation: {_RECOMMENDATION[self.severity]}")
        return "\n".join(lines) + "\n"


def slo_assessment_from_dict(data: dict) -> SloAssessment:
    """Build a SloAssessment from a JSON-ish dict; unknown keys are ignored."""
    return SloAssessment(
        slo_target=data.get("slo_target", 0.999),
        observed_error_ratio=data.get("observed_error_ratio", 0.0),
        window_hours=data.get("window_hours", 720.0),
        elapsed_hours=data.get(
            "elapsed_hours", data.get("window_hours", 720.0)
        ),
    )
