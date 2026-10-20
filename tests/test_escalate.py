import pytest

from sre_toolkit.escalate import (
    EscalationBook,
    EscalationLevel,
    EscalationPolicy,
    escalation_book_from_dict,
)

BOOK_DATA = {
    "policies": {
        "SEV-1": {
            "name": "sev1-core",
            "levels": [
                {"wait_minutes": 5, "targets": ["primary-oncall"]},
                {"wait_minutes": 15, "targets": ["secondary-oncall", "eng-manager"]},
                {"wait_minutes": 0, "targets": ["vp-eng"]},
            ],
        },
        "SEV-2": {
            "levels": [
                {"wait_minutes": 30, "targets": ["primary-oncall"]},
                {"wait_minutes": 0, "targets": ["eng-manager"]},
            ]
        },
    },
    "default": "SEV-2",
}


def _book() -> EscalationBook:
    return escalation_book_from_dict(BOOK_DATA)


def test_first_level_at_start():
    state = _book().resolve("SEV-1", 0)
    assert state.level_index == 0
    assert state.targets == ["primary-oncall"]
    assert state.next_in == 5
    assert state.is_final is False


def test_boundary_escalates_at_wait_end():
    state = _book().resolve("SEV-1", 5)
    assert state.level_index == 1
    assert state.targets == ["secondary-oncall", "eng-manager"]
    assert state.next_in == 15


def test_mid_level_next_in_counts_down():
    state = _book().resolve("SEV-1", 12)
    assert state.level_index == 1
    assert state.next_in == 8


def test_final_level_persists_forever():
    state = _book().resolve("SEV-1", 10_000)
    assert state.level_index == 2
    assert state.targets == ["vp-eng"]
    assert state.next_in is None
    assert state.is_final is True


def test_severity_is_case_insensitive():
    assert _book().resolve("sev-1", 0).level_index == 0


def test_unknown_severity_falls_back_to_default():
    state = _book().resolve("SEV-9", 10)
    assert state.policy.name == "SEV-2"
    assert state.targets == ["primary-oncall"]


def test_unknown_severity_without_default_raises():
    book = escalation_book_from_dict({"policies": BOOK_DATA["policies"]})
    with pytest.raises(ValueError):
        book.resolve("SEV-9", 0)


def test_negative_elapsed_raises():
    with pytest.raises(ValueError):
        _book().resolve("SEV-1", -1)


def test_policy_needs_at_least_one_level():
    with pytest.raises(ValueError):
        EscalationPolicy(name="empty", levels=[])


def test_policy_rejects_negative_wait():
    with pytest.raises(ValueError):
        EscalationPolicy(
            name="bad", levels=[EscalationLevel(wait_minutes=-5, targets=[])]
        )


def test_from_dict_normalizes_severity_keys():
    book = escalation_book_from_dict(
        {"policies": {"sev-3": {"levels": [{"wait_minutes": 10, "targets": []}]}}}
    )
    assert "SEV-3" in book.policies


def test_from_dict_ignores_unknown_keys():
    book = escalation_book_from_dict({**BOOK_DATA, "bogus": True})
    assert book.default == "SEV-2"


def test_level_window():
    policy = _book().policies["SEV-1"]
    assert policy.level_window(0) == (0, 5)
    assert policy.level_window(1) == (5, 20)
    assert policy.level_window(2) == (20, None)


def test_markdown_shows_current_position():
    md = _book().resolve("SEV-1", 12).to_markdown()
    assert "# Escalation: sev1-core" in md
    assert "Current level: 2 of 3" in md
    assert "secondary-oncall, eng-manager" in md
    assert "Next escalation: in 8m" in md
    assert "[>] Level 2 (5-20m)" in md


def test_markdown_final_level():
    md = _book().resolve("SEV-1", 60).to_markdown()
    assert "Next escalation: none (final level)" in md
    assert "[>] Level 3 (20m+)" in md
