"""Run incidents from checklists instead of memory.

A Runbook is an ordered list of steps with owners. Mark steps done as you
go and render the whole thing as Markdown for the incident channel.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Step:
    title: str
    owner: str = "on-call"
    done: bool = False
    note: str = ""


@dataclass
class Runbook:
    title: str
    steps: list[Step] = field(default_factory=list)

    def add_step(self, title: str, owner: str = "on-call") -> Step:
        step = Step(title=title, owner=owner)
        self.steps.append(step)
        return step

    def complete(self, index: int, note: str = "") -> None:
        """Mark the step at ``index`` done, optionally with a note."""
        step = self.steps[index]
        step.done = True
        if note:
            step.note = note

    @property
    def progress(self) -> float:
        """Fraction of steps completed (1.0 when empty -- nothing to do)."""
        if not self.steps:
            return 1.0
        return sum(1 for s in self.steps if s.done) / len(self.steps)

    @property
    def next_step(self) -> Step | None:
        """First incomplete step, or None when the runbook is finished."""
        return next((s for s in self.steps if not s.done), None)

    def to_markdown(self) -> str:
        lines = [f"# {self.title}", ""]
        for i, step in enumerate(self.steps, 1):
            box = "x" if step.done else " "
            lines.append(f"- [{box}] {i}. {step.title} (owner: {step.owner})")
            if step.note:
                lines.append(f"  > {step.note}")
        lines.append("")
        lines.append(f"Progress: {self.progress:.0%} ({sum(s.done for s in self.steps)}/{len(self.steps)})")
        return "\n".join(lines)


def db_failover_runbook() -> Runbook:
    """Example: the runbook you wish you had during a primary DB failover."""
    rb = Runbook("Database primary failover")
    rb.add_step("Confirm primary is unhealthy (3 consecutive failed health checks)", owner="on-call")
    rb.add_step("Page DBA secondary", owner="on-call")
    rb.add_step("Promote replica: `pg_ctl promote -D /var/lib/postgres/data`", owner="dba")
    rb.add_step("Update connection strings / service discovery", owner="on-call")
    rb.add_step("Verify writes succeed on new primary", owner="on-call")
    rb.add_step("Open incident channel thread with timeline", owner="comms")
    return rb
