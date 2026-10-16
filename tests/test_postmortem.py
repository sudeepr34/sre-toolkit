import json

from sre_toolkit.cli import main
from sre_toolkit.postmortem import Postmortem, postmortem_from_dict


def test_empty_postmortem_renders_template():
    md = Postmortem().to_markdown()
    assert "# Postmortem: untitled incident" in md
    assert "## Summary" in md
    assert "## Timeline" in md
    assert "- _No timeline events yet._" in md
    assert "## Contributing factors" in md
    assert "## What went well" in md
    assert "## Action items (0 open)" in md


def test_timeline_sorts_by_timestamp():
    pm = Postmortem(title="db outage")
    pm.add_event("2026-10-14T09:50:00", "failover complete")
    pm.add_event("2026-10-14T09:46:00", "primary unhealthy", milestone="detected")
    md = pm.to_markdown()
    assert md.index("primary unhealthy") < md.index("failover complete")


def test_milestones_render_tags_and_metrics():
    pm = Postmortem(title="db outage")
    pm.add_event("2026-10-14T09:46:00", "primary unhealthy", milestone="detected")
    pm.add_event("2026-10-14T10:28:00", "traffic on replica", milestone="mitigated")
    pm.add_event("2026-10-14T12:01:00", "primary rebuilt", milestone="resolved")
    md = pm.to_markdown()
    assert "**[DETECTED]**" in md
    assert "**[MITIGATED]**" in md
    assert "**[RESOLVED]**" in md
    assert "- Time to mitigate: 42m" in md
    assert "- Time to resolve: 2h 15m" in md


def test_missing_milestones_omit_metrics():
    pm = Postmortem(title="weird one")
    pm.add_event("2026-10-14T09:46:00", "something happened")
    md = pm.to_markdown()
    assert "## Key metrics" not in md
    assert pm.time_to_mitigate is None
    assert pm.time_to_resolve is None


def test_unparseable_timestamps_omit_metrics():
    pm = Postmortem(title="sloppy log")
    pm.add_event("yesterday-ish", "alerts fired", milestone="detected")
    pm.add_event("later", "fixed", milestone="mitigated")
    md = pm.to_markdown()
    assert "## Key metrics" not in md


def test_action_items_track_open_count():
    pm = Postmortem(title="db outage")
    pm.add_action_item("add replica lag alert", owner="sudeep", due="Fri")
    item = pm.add_action_item("document failover steps", owner="priya")
    item.done = True
    md = pm.to_markdown()
    assert "## Action items (1 open)" in md
    assert "- [ ] add replica lag alert (owner: sudeep, due: Fri)" in md
    assert "- [x] document failover steps (owner: priya)" in md


def test_from_dict_builds_sections_and_ignores_unknown_keys():
    pm = postmortem_from_dict(
        {
            "title": "cache stampede",
            "date": "2026-10-13",
            "severity": "SEV-2",
            "summary": "hot key took down the cache tier",
            "timeline": [
                {
                    "timestamp": "2026-10-13T14:02:00",
                    "title": "p99 latency spike",
                    "milestone": "detected",
                }
            ],
            "contributing_factors": ["no request coalescing"],
            "went_well": ["on-call paged in 3 minutes"],
            "action_items": [{"task": "add coalescing", "owner": "sudeep"}],
            "unknown_key": "ignored",
        }
    )
    assert pm.title == "cache stampede"
    assert pm.severity == "SEV-2"
    assert len(pm.timeline) == 1
    assert pm.timeline[0].milestone == "detected"
    assert pm.contributing_factors == ["no request coalescing"]
    assert pm.went_well == ["on-call paged in 3 minutes"]
    assert pm.action_items[0].owner == "sudeep"
    md = pm.to_markdown()
    assert "# Postmortem: cache stampede" in md
    assert "hot key took down the cache tier" in md


def test_postmortem_command_renders_file(tmp_path, capsys):
    payload = {
        "title": "db outage",
        "severity": "SEV-1",
        "timeline": [
            {
                "timestamp": "2026-10-14T09:46:00",
                "title": "primary unhealthy",
                "milestone": "detected",
            }
        ],
    }
    path = tmp_path / "incident.json"
    path.write_text(json.dumps(payload))
    rc = main(["postmortem", "--file", str(path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# Postmortem: db outage" in out
    assert "Severity: SEV-1" in out
    assert "**[DETECTED]**" in out


def test_postmortem_command_without_file_prints_template(capsys):
    rc = main(["postmortem", "--title", "next incident", "--severity", "SEV-2"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# Postmortem: next incident" in out
    assert "Severity: SEV-2" in out
    assert "- _No timeline events yet._" in out
