from sre_toolkit.handoff import Handoff, handoff_from_dict


def test_to_markdown_renders_sections():
    handoff = Handoff(shift="2026-10-12", outgoing="priya", incoming="sudeep")
    handoff.add_incident("DB latency spike", severity="SEV-2", owner="priya")
    handoff.watch_items.append("disk usage on db-1 trending up")
    handoff.add_follow_up("rotate the pagerduty schedule", owner="sudeep", due="Tue")
    md = handoff.to_markdown()
    assert "# On-call handoff: 2026-10-12" in md
    assert "- Outgoing: priya" in md
    assert "- Incoming: sudeep" in md
    assert "- [SEV-2] DB latency spike (mitigated, owner: priya)" in md
    assert "- disk usage on db-1 trending up" in md
    assert "- rotate the pagerduty schedule (owner: sudeep, due: Tue)" in md


def test_empty_handoff_renders_nones():
    md = Handoff().to_markdown()
    assert md.count("- None") == 4


def test_open_count_ignores_resolved():
    handoff = Handoff()
    handoff.add_incident("still open", status="mitigated")
    handoff.add_incident("all done", status="resolved")
    assert handoff.open_count == 1


def test_from_dict_builds_sections():
    handoff = handoff_from_dict(
        {
            "shift": "2026-10-12",
            "outgoing": "priya",
            "open_incidents": [
                {"title": "pod crashlooping", "severity": "SEV-3", "status": "open"}
            ],
            "watch_items": ["node-3 memory pressure"],
            "follow_ups": [{"task": "page the vendor", "owner": "sudeep"}],
            "recent_changes": ["deployed api v1.4.2"],
            "unknown_key": "ignored",
        }
    )
    assert handoff.shift == "2026-10-12"
    assert handoff.outgoing == "priya"
    assert handoff.incoming == "on-call"
    assert len(handoff.open_incidents) == 1
    assert handoff.open_incidents[0].title == "pod crashlooping"
    assert handoff.watch_items == ["node-3 memory pressure"]
    assert handoff.follow_ups[0].owner == "sudeep"
    assert handoff.recent_changes == ["deployed api v1.4.2"]
    md = handoff.to_markdown()
    assert "- [SEV-3] pod crashlooping (open, owner: on-call)" in md
