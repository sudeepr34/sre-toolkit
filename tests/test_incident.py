from datetime import datetime

import pytest

from sre_toolkit.incident import Incident, IncidentStore


def _store(tmp_path) -> IncidentStore:
    return IncidentStore(str(tmp_path / "incidents.json"))


def test_start_assigns_sequential_ids(tmp_path):
    store = _store(tmp_path)
    first = store.start("db outage", severity="SEV-1")
    second = store.start("slow api")
    assert first.id == "INC-0001"
    assert second.id == "INC-0002"
    assert first.status == "open"
    assert first.severity == "SEV-1"


def test_start_records_opened_entry(tmp_path):
    store = _store(tmp_path)
    incident = store.start("db outage", started="2026-10-23T09:00")
    assert incident.timeline[0].kind == "opened"
    assert "SEV-3" in incident.timeline[0].text


def test_elapsed_seconds(tmp_path):
    store = _store(tmp_path)
    incident = store.start("db outage", started="2026-10-23T09:00")
    elapsed = incident.elapsed_seconds(datetime.fromisoformat("2026-10-23T09:45"))
    assert elapsed == 45 * 60


def test_elapsed_none_for_bad_start():
    incident = Incident(id="INC-0001", title="x", started="soon")
    assert incident.elapsed_seconds() is None


def test_add_note_appends(tmp_path):
    store = _store(tmp_path)
    incident = store.start("db outage")
    incident.add_note("looking at dashboards", timestamp="2026-10-23T09:10")
    assert incident.timeline[-1].kind == "note"
    assert incident.timeline[-1].text == "looking at dashboards"


def test_set_status_transitions(tmp_path):
    store = _store(tmp_path)
    incident = store.start("db outage")
    incident.set_status("acknowledged", timestamp="2026-10-23T09:05")
    assert incident.status == "acknowledged"
    assert incident.timeline[-1].text == "status -> acknowledged"


def test_set_status_rejects_unknown(tmp_path):
    store = _store(tmp_path)
    incident = store.start("db outage")
    with pytest.raises(ValueError):
        incident.set_status("vibing")


def test_resolve_closes_incident(tmp_path):
    store = _store(tmp_path)
    incident = store.start("db outage")
    incident.resolve(timestamp="2026-10-23T10:00")
    assert incident.status == "resolved"
    assert incident.is_open is False
    assert incident.timeline[-1].kind == "resolved"


def test_list_open_excludes_resolved(tmp_path):
    store = _store(tmp_path)
    first = store.start("one")
    store.start("two")
    first.resolve()
    assert [i.id for i in store.list_open()] == ["INC-0002"]


def test_get_is_case_insensitive(tmp_path):
    store = _store(tmp_path)
    store.start("db outage")
    assert store.get("inc-0001").title == "db outage"


def test_get_unknown_id_raises(tmp_path):
    with pytest.raises(ValueError):
        _store(tmp_path).get("INC-9999")


def test_store_persists_across_instances(tmp_path):
    path = str(tmp_path / "incidents.json")
    store = IncidentStore(path)
    store.start("db outage", severity="SEV-2")
    reopened = IncidentStore(path)
    assert reopened.get("INC-0001").severity == "SEV-2"
    assert reopened.start("next").id == "INC-0002"


def test_store_ignores_corrupt_file(tmp_path):
    path = tmp_path / "incidents.json"
    path.write_text("not json{{{")
    store = IncidentStore(str(path))
    assert store.list_open() == []


def test_markdown_shows_status_and_elapsed(tmp_path):
    store = _store(tmp_path)
    incident = store.start("db outage", severity="SEV-1", started="2026-10-23T09:00")
    md = incident.to_markdown(datetime.fromisoformat("2026-10-23T09:45"))
    assert "# Incident INC-0001: db outage" in md
    assert "**open**" in md
    assert "Elapsed: 45m" in md
    assert "## Timeline" in md


def test_round_trip_dict(tmp_path):
    store = _store(tmp_path)
    incident = store.start("db outage", severity="SEV-2")
    incident.add_note("n1", timestamp="2026-10-23T09:10")
    clone = Incident.from_dict(incident.to_dict())
    assert clone.id == incident.id
    assert clone.timeline[-1].text == "n1"
