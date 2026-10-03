from sre_toolkit.handoff import Handoff


def test_open_count_tracks_status():
    h = Handoff(author="sudeep", shift_date="2026-10-04")
    h.add("db failover follow-up", status="open")
    h.add("tls cert renewed", status="resolved")
    assert h.open_count == 1


def test_to_markdown_includes_items_and_watch():
    h = Handoff(author="sudeep", shift_date="2026-10-04")
    h.add("slow query on orders db", status="mitigated", owner="dba")
    h.watch("deploys frozen until 10am")
    md = h.to_markdown()
    assert "# On-call handoff" in md
    assert "slow query on orders db" in md
    assert "deploys frozen until 10am" in md
    assert "Open items: 0" in md


def test_quiet_shift_renders():
    md = Handoff(author="sudeep").to_markdown()
    assert "quiet shift" in md
