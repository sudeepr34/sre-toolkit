import pytest

from sre_toolkit.comms import (
    STATUSES,
    StatusPage,
    StatusUpdate,
    status_page_from_dict,
)


def _page(**overrides):
    base = {
        "title": "Checkout API errors",
        "status": "investigating",
        "severity": "SEV-2",
        "affected": ["checkout-api", "payments-worker"],
        "started": "2026-10-19T09:00",
        "updates": [
            {
                "timestamp": "2026-10-19T09:00",
                "status": "investigating",
                "message": "Error rate spiking; paging the team.",
            },
            {
                "timestamp": "2026-10-19T09:45",
                "status": "identified",
                "message": "Root cause found in deploy 4521; rolling back.",
            },
        ],
    }
    base.update(overrides)
    return status_page_from_dict(base)


def test_from_dict_title_and_status():
    page = _page()
    assert page.title == "Checkout API errors"
    assert page.status == "investigating"
    assert page.severity == "SEV-2"


def test_from_dict_defaults():
    page = status_page_from_dict({})
    assert page.title == "untitled incident"
    assert page.status == "investigating"
    assert page.severity == "SEV-3"
    assert page.affected == []
    assert page.updates == []


def test_from_dict_rejects_unknown_status():
    with pytest.raises(ValueError):
        status_page_from_dict({"status": "vibing"})


def test_from_dict_rejects_unknown_update_status():
    with pytest.raises(ValueError):
        status_page_from_dict(
            {"updates": [{"timestamp": "t", "status": "doom", "message": "m"}]}
        )


def test_from_dict_status_is_case_insensitive():
    page = _page(status="Monitoring")
    assert page.status == "monitoring"


def test_from_dict_affected_string_becomes_list():
    page = _page(affected="checkout-api")
    assert page.affected == ["checkout-api"]


def test_from_dict_ignores_unknown_keys():
    page = _page(bogus=True)
    assert page.title == "Checkout API errors"


def test_updates_sorted_newest_first():
    page = _page()
    ordered = page.ordered_updates()
    assert [u.timestamp for u in ordered] == [
        "2026-10-19T09:45",
        "2026-10-19T09:00",
    ]


def test_unparsable_timestamps_sink_to_end():
    page = _page(
        updates=[
            {"timestamp": "soon", "status": "monitoring", "message": "m"},
            {"timestamp": "2026-10-19T09:00", "status": "investigating", "message": "m"},
        ]
    )
    assert page.ordered_updates()[-1].timestamp == "soon"


def test_markdown_has_banner_and_sections():
    md = _page().to_markdown()
    assert md.startswith("# Checkout API errors")
    assert "**investigating**" in md
    assert "SEV-2" in md
    assert "checkout-api, payments-worker" in md
    assert "## Updates" in md
    # Newest update first in the rendered timeline section.
    first = md.index("### 2026-10-19T09:45")
    second = md.index("### 2026-10-19T09:00")
    assert first < second


def test_markdown_update_headings_carry_status():
    md = _page().to_markdown()
    assert "### 2026-10-19T09:45 — identified" in md


def test_markdown_empty_updates():
    md = _page(updates=[]).to_markdown()
    assert "No updates published yet" in md


def test_markdown_shows_resolved_line():
    md = _page(status="resolved", resolved="2026-10-19T10:30").to_markdown()
    assert "Resolved: 2026-10-19T10:30" in md


def test_markdown_shows_next_update():
    md = _page(next_update="10:30 IST").to_markdown()
    assert "Next update: 10:30 IST" in md


def test_markdown_omits_empty_optional_lines():
    md = status_page_from_dict({"title": "x"}).to_markdown()
    assert "Started:" not in md
    assert "Resolved:" not in md
    assert "Impacted:" not in md


def test_all_statuses_round_trip():
    for status in STATUSES:
        page = _page(status=status)
        assert page.status == status
        assert f"**{status}**" in page.to_markdown()


def test_direct_status_update_dataclass():
    update = StatusUpdate(timestamp="t", status="monitoring", message=" m ")
    page = StatusPage(title="t", updates=[update])
    assert "m" in page.to_markdown()
