from sre_toolkit.brief import brief_markdown
from sre_toolkit.handoff import Handoff


def _alerts():
    return [
        {"name": "HighErrorRate", "labels": {"service": "api"}, "timestamp": "t1"},
        {"name": "HighErrorRate", "labels": {"service": "api"}, "timestamp": "t2"},
        {"name": "DiskFull", "labels": {"host": "db-1"}, "timestamp": "t1"},
    ]


def test_brief_alerts_only():
    md = brief_markdown(_alerts(), shift="2026-10-13")
    assert "# Shift brief: 2026-10-13" in md
    assert "## Alert noise" in md
    assert "- Total: 3 (2 unique)" in md
    assert "- Duplicates suppressed: 1" in md
    assert "- [2x] HighErrorRate" in md
    assert "## Carried over" not in md


def test_brief_defaults_shift_label():
    md = brief_markdown([])
    assert "# Shift brief: this shift" in md
    assert "- Total: 0 (0 unique)" in md
    assert "- Flapping: none" in md


def test_brief_carryover_sections():
    handoff = Handoff(shift="2026-10-12", outgoing="priya", incoming="sudeep")
    handoff.add_incident("checkout 500s", severity="SEV-2", status="open")
    handoff.add_incident("cron lag", severity="SEV-4", status="mitigated")
    handoff.add_incident("old disk issue", severity="SEV-3", status="resolved")
    handoff.watch_items.append("db-1 disk trending up")
    handoff.add_follow_up("page the vendor", owner="sudeep", due="Wed")
    md = brief_markdown(_alerts(), handoff=handoff, shift="2026-10-13")
    assert "## Carried over" in md
    # resolved incidents are excluded; SEV-2 sorts above SEV-4
    assert "### Open incidents (2)" in md
    sev2 = md.index("**SEV-2** checkout 500s")
    sev4 = md.index("**SEV-4** cron lag")
    assert sev2 < sev4
    assert "old disk issue" not in md
    assert "### Watch items (1)" in md
    assert "- db-1 disk trending up" in md
    assert "### Follow-ups (1)" in md
    assert "- [ ] page the vendor — sudeep (due: Wed)" in md


def test_brief_empty_handoff_renders_nones():
    md = brief_markdown([], handoff=Handoff())
    assert "### Open incidents (0)" in md
    assert md.count("- none") == 3
