from sre_toolkit.runbook import Runbook, db_failover_runbook


def test_progress_tracks_completion():
    rb = Runbook("demo")
    rb.add_step("one")
    rb.add_step("two")
    assert rb.progress == 0.0
    rb.complete(0)
    assert rb.progress == 0.5
    rb.complete(1, note="verified")
    assert rb.progress == 1.0


def test_next_step_skips_done():
    rb = Runbook("demo")
    rb.add_step("one")
    rb.add_step("two")
    rb.complete(0)
    assert rb.next_step.title == "two"
    rb.complete(1)
    assert rb.next_step is None


def test_to_markdown_renders_checklist():
    rb = Runbook("demo")
    rb.add_step("one", owner="sre")
    rb.complete(0, note="ok")
    md = rb.to_markdown()
    assert "# demo" in md
    assert "- [x] 1. one (owner: sre)" in md
    assert "> ok" in md
    assert "Progress: 100% (1/1)" in md


def test_empty_runbook_is_complete():
    assert Runbook("empty").progress == 1.0


def test_db_failover_runbook_has_steps():
    rb = db_failover_runbook()
    assert len(rb.steps) == 6
    assert rb.next_step.owner == "on-call"
