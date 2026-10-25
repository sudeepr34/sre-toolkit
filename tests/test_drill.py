import pytest

from sre_toolkit.drill import get_scenario, list_scenarios


def test_list_has_six_scenarios():
    scenarios = list_scenarios()
    assert len(scenarios) == 6
    ids = {s.id for s in scenarios}
    assert ids == {
        "db-failover", "cache-outage", "az-loss",
        "disk-full", "cert-expiry", "bad-deploy",
    }


def test_get_scenario_case_insensitive():
    assert get_scenario("DB-FAILOVER").title == "Primary database failover"


def test_get_unknown_scenario_lists_known():
    with pytest.raises(ValueError) as excinfo:
        get_scenario("meteor-strike")
    assert "db-failover" in str(excinfo.value)


def test_scenario_markdown_has_steps_criteria_rollback():
    md = get_scenario("db-failover").to_markdown()
    assert "# Drill: Primary database failover" in md
    assert "Promote the replica to primary" in md
    assert "No user-visible data loss" in md
    assert "## Rollback" in md
    assert "Fail back to the original primary" in md


def test_every_scenario_has_steps_and_criteria():
    for scenario in list_scenarios():
        assert scenario.steps, scenario.id
        assert scenario.success_criteria, scenario.id
        assert scenario.duration_minutes > 0, scenario.id


def test_run_sheet_checkboxes_and_date():
    sheet = get_scenario("disk-full").run_sheet(run_date="2026-10-25")
    assert "# Drill run: Disk pressure on a node" in sheet
    assert "Date: 2026-10-25" in sheet
    assert "- [ ] [on-call] Confirm the disk-pressure alert fired" in sheet
    assert "- [ ] Pass" in sheet
    assert "## Notes" in sheet


def test_run_sheet_defaults_to_today():
    sheet = get_scenario("az-loss").run_sheet()
    assert "Date: " in sheet
    assert "Date: \n" not in sheet
