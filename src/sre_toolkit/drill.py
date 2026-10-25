"""Game-day exercise plans.

A small library of failure scenarios an SRE team can rehearse: each one
carries a step-by-step checklist, success criteria, and a rollback note.
`run` prints a dated run sheet the team can work through and file next
to the postmortem.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class DrillStep:
    action: str
    expected: str = ""
    owner: str = "on-call"


@dataclass
class DrillScenario:
    id: str
    title: str
    blast_radius: str
    duration_minutes: int
    steps: list = field(default_factory=list)
    success_criteria: list = field(default_factory=list)
    rollback: str = ""

    def to_markdown(self) -> str:
        lines = [f"# Drill: {self.title}", ""]
        lines.append(f"- Scenario: `{self.id}`")
        lines.append(f"- Blast radius: {self.blast_radius}")
        lines.append(f"- Planned duration: {self.duration_minutes} minutes")
        lines.append("")
        lines.append("## Steps")
        for i, step in enumerate(self.steps, 1):
            lines.append(f"{i}. [{step.owner}] {step.action}")
            if step.expected:
                lines.append(f"   Expected: {step.expected}")
        lines.append("")
        lines.append("## Success criteria")
        for criterion in self.success_criteria:
            lines.append(f"- {criterion}")
        if self.rollback:
            lines.append("")
            lines.append(f"## Rollback\n{self.rollback}")
        return "\n".join(lines) + "\n"

    def run_sheet(self, run_date: str = "") -> str:
        lines = [f"# Drill run: {self.title}", ""]
        lines.append(f"- Scenario: `{self.id}` | Date: {run_date or date.today().isoformat()}")
        lines.append(f"- Blast radius: {self.blast_radius}")
        lines.append("")
        lines.append("## Checklist")
        for step in self.steps:
            lines.append(f"- [ ] [{step.owner}] {step.action}")
        lines.append("")
        lines.append("## Outcome")
        lines.append("- [ ] Pass  - [ ] Partial  - [ ] Fail")
        lines.append("")
        lines.append("## Notes")
        lines.append("_Record what broke, what surprised you, and follow-ups here._")
        return "\n".join(lines) + "\n"


SCENARIOS = [
    DrillScenario(
        id="db-failover",
        title="Primary database failover",
        blast_radius="one service's reads/writes",
        duration_minutes=60,
        steps=[
            DrillStep("Stop writes to the primary", "writes queue or error cleanly", "on-call"),
            DrillStep("Promote the replica to primary", "replica accepts writes", "dba"),
            DrillStep("Point the app at the new primary", "error rate returns to baseline", "on-call"),
            DrillStep("Verify no data loss in the last checkpoint", "replication lag at failover < 1s", "dba"),
        ],
        success_criteria=[
            "Failover completes within the SLO error budget",
            "No user-visible data loss",
            "Alerts fired before the team noticed manually",
        ],
        rollback="Fail back to the original primary once it is healthy and caught up.",
    ),
    DrillScenario(
        id="cache-outage",
        title="Cache layer outage",
        blast_radius="read latency for one service",
        duration_minutes=45,
        steps=[
            DrillStep("Take the cache tier out of rotation", "traffic falls back to the database", "on-call"),
            DrillStep("Watch database load and latency", "p99 stays within SLO", "on-call"),
            DrillStep("Restore the cache tier gradually", "hit rate recovers without a thundering herd", "on-call"),
        ],
        success_criteria=[
            "Service stays up on database reads alone",
            "No cascading overload on the database",
        ],
        rollback="Re-enable the cache tier and warm it before full traffic returns.",
    ),
    DrillScenario(
        id="az-loss",
        title="Availability zone loss",
        blast_radius="one zone of a multi-zone service",
        duration_minutes=60,
        steps=[
            DrillStep("Drain traffic from the zone", "remaining zones absorb load", "on-call"),
            DrillStep("Confirm auto-scaling replaces lost capacity", "replica count recovers", "on-call"),
            DrillStep("Verify cross-zone dependencies still resolve", "no hard dependency on the lost zone", "on-call"),
        ],
        success_criteria=[
            "No user-visible outage",
            "Capacity recovers without manual instance launches",
        ],
        rollback="Re-admit the zone once its health checks pass.",
    ),
    DrillScenario(
        id="disk-full",
        title="Disk pressure on a node",
        blast_radius="one node",
        duration_minutes=30,
        steps=[
            DrillStep("Confirm the disk-pressure alert fired", "alert names the node and mount", "on-call"),
            DrillStep("Rotate or drop non-essential logs", "disk usage drops below 80%", "on-call"),
            DrillStep("Cordon the node if workloads are at risk", "pods reschedule cleanly", "on-call"),
        ],
        success_criteria=[
            "Alert fired before the disk hit 100%",
            "Node recovered without a workload outage",
        ],
        rollback="Uncordon the node after usage stabilizes.",
    ),
    DrillScenario(
        id="cert-expiry",
        title="TLS certificate expiry",
        blast_radius="one public endpoint",
        duration_minutes=45,
        steps=[
            DrillStep("Stage a certificate expiring within the hour", "expiry alert fires", "on-call"),
            DrillStep("Rotate the certificate", "new cert serves without a restart outage", "on-call"),
            DrillStep("Verify clients accept the new chain", "TLS handshake success rate returns to 100%", "on-call"),
        ],
        success_criteria=[
            "Expiry alert fired with enough lead time",
            "Rotation caused zero failed handshakes",
        ],
        rollback="Re-issue from the previous certificate if clients reject the new chain.",
    ),
    DrillScenario(
        id="bad-deploy",
        title="Bad deploy rollback",
        blast_radius="canary slice, then full fleet if missed",
        duration_minutes=45,
        steps=[
            DrillStep("Ship a canary with an injected error", "canary error rate spikes", "on-call"),
            DrillStep("Confirm automated rollback triggers", "canary reverts without manual action", "release-manager"),
            DrillStep("Verify the fleet is on the last good version", "version metric matches the previous release", "on-call"),
        ],
        success_criteria=[
            "Canary caught the regression before full rollout",
            "Rollback completed within the deploy SLO",
        ],
        rollback="Manual rollback to the previous release if automation does not trigger.",
    ),
]


def list_scenarios() -> list:
    return list(SCENARIOS)


def get_scenario(scenario_id: str) -> DrillScenario:
    for scenario in SCENARIOS:
        if scenario.id == scenario_id.lower():
            return scenario
    known = ", ".join(s.id for s in SCENARIOS)
    raise ValueError(f"unknown drill scenario {scenario_id!r}; known: {known}")
