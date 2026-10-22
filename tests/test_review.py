from sre_toolkit.postmortem import postmortem_from_dict
from sre_toolkit.review import WeeklyReview, weekly_review_from_postmortems


def _pm(**overrides):
    base = {
        "title": "db outage",
        "severity": "SEV-1",
        "timeline": [
            {"timestamp": "2026-10-20T09:00", "title": "alert", "milestone": "detected"},
            {"timestamp": "2026-10-20T09:30", "title": "rollback", "milestone": "mitigated"},
            {"timestamp": "2026-10-20T10:00", "title": "healthy", "milestone": "resolved"},
        ],
        "contributing_factors": ["bad deploy", "missing alert"],
        "action_items": [
            {"task": "add canary", "owner": "sudeep", "done": False},
            {"task": "fix alert", "owner": "priya", "done": True},
        ],
    }
    base.update(overrides)
    return postmortem_from_dict(base)


def test_counts_and_severity_breakdown():
    review = WeeklyReview(
        week="2026-W42",
        postmortems=[_pm(), _pm(title="slow api", severity="SEV-2")],
    )
    assert review.count == 2
    assert review.by_severity() == {"SEV-1": 1, "SEV-2": 1}


def test_mean_ttm_and_ttr():
    review = WeeklyReview(
        postmortems=[
            _pm(),  # TTM 30m, TTR 60m
            _pm(
                title="quick one",
                timeline=[
                    {"timestamp": "2026-10-21T09:00", "title": "a", "milestone": "detected"},
                    {"timestamp": "2026-10-21T09:10", "title": "b", "milestone": "mitigated"},
                    {"timestamp": "2026-10-21T09:20", "title": "c", "milestone": "resolved"},
                ],
            ),  # TTM 10m, TTR 20m
        ]
    )
    assert review.mean_time_to_mitigate == 20 * 60  # (30m + 10m) / 2
    assert review.mean_time_to_resolve == 40 * 60  # (60m + 20m) / 2


def test_means_skip_incidents_without_milestones():
    review = WeeklyReview(postmortems=[_pm(timeline=[])])
    assert review.mean_time_to_mitigate is None
    assert review.mean_time_to_resolve is None


def test_top_factors_ranked():
    review = WeeklyReview(
        postmortems=[
            _pm(contributing_factors=["bad deploy", "missing alert"]),
            _pm(contributing_factors=["bad deploy"]),
        ]
    )
    assert review.top_factors() == [("bad deploy", 2), ("missing alert", 1)]


def test_open_action_items_only_open_ones():
    review = WeeklyReview(postmortems=[_pm()])
    actions = review.open_action_items()
    assert len(actions) == 1
    title, item = actions[0]
    assert title == "db outage"
    assert item.task == "add canary"
    assert item.owner == "sudeep"


def test_markdown_full_review():
    md = WeeklyReview(week="2026-W42", postmortems=[_pm()]).to_markdown()
    assert "# Ops review: 2026-W42" in md
    assert "Incidents reviewed: 1" in md
    assert "SEV-1: 1" in md
    assert "Mean time to mitigate: 30m" in md
    assert "Mean time to resolve: 1h" in md
    assert "[1x] bad deploy" in md
    assert "## Open action items (1)" in md
    assert "add canary" in md
    assert "fix alert" not in md  # done items stay out


def test_markdown_empty_week():
    md = WeeklyReview(week="2026-W42", postmortems=[]).to_markdown()
    assert "Incidents reviewed: 0" in md
    assert "No incidents this week" in md


def test_markdown_untitled_week():
    md = WeeklyReview(postmortems=[_pm()]).to_markdown()
    assert md.startswith("# Ops review: week")


def test_from_postmortems_builder():
    pms = [_pm(), _pm(title="other")]
    review = weekly_review_from_postmortems(pms, week="2026-W42")
    assert review.count == 2
    assert review.week == "2026-W42"
