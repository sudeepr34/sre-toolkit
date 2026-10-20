"""On-call escalation policy resolution.

Given an escalation policy (ordered levels, each with a wait time and the
targets to page), an incident severity, and how long the incident has
been running, resolves who should be paged *now*, and when the next
escalation fires. Policies are keyed by severity with a default fallback.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EscalationLevel:
    """One rung of an escalation ladder.

    ``wait_minutes`` is how long this level stays current before the
    incident escalates to the next level.
    """

    wait_minutes: int
    targets: list = field(default_factory=list)


@dataclass
class EscalationPolicy:
    name: str
    levels: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.levels:
            raise ValueError(f"policy {self.name!r} needs at least one level")
        for level in self.levels:
            if level.wait_minutes < 0:
                raise ValueError("wait_minutes must be >= 0")

    def state_at(self, elapsed_minutes: int) -> "EscalationState":
        """Resolve the ladder position ``elapsed_minutes`` into the incident."""
        if elapsed_minutes < 0:
            raise ValueError(f"elapsed_minutes must be >= 0, got {elapsed_minutes}")
        start = 0
        for index, level in enumerate(self.levels):
            end = start + level.wait_minutes
            is_last = index == len(self.levels) - 1
            if is_last or elapsed_minutes < end:
                return EscalationState(
                    policy=self,
                    elapsed_minutes=elapsed_minutes,
                    level_index=index,
                    next_in=None if is_last else end - elapsed_minutes,
                )
            start = end
        raise AssertionError("unreachable")

    def level_window(self, index: int) -> tuple[int, int | None]:
        """(start, end) minutes of a level; end is None for the last level."""
        start = sum(level.wait_minutes for level in self.levels[:index])
        if index == len(self.levels) - 1:
            return start, None
        return start, start + self.levels[index].wait_minutes


@dataclass
class EscalationState:
    policy: EscalationPolicy
    elapsed_minutes: int
    level_index: int
    next_in: int | None

    @property
    def level(self) -> EscalationLevel:
        return self.policy.levels[self.level_index]

    @property
    def targets(self) -> list:
        return self.level.targets

    @property
    def is_final(self) -> bool:
        return self.level_index == len(self.policy.levels) - 1

    def to_markdown(self) -> str:
        lines = [f"# Escalation: {self.policy.name}", ""]
        lines.append(f"- Elapsed: {self.elapsed_minutes}m")
        lines.append(
            f"- Current level: {self.level_index + 1} of {len(self.policy.levels)}"
        )
        targets = ", ".join(self.targets) if self.targets else "(nobody)"
        lines.append(f"- Page now: {targets}")
        if self.next_in is None:
            lines.append("- Next escalation: none (final level)")
        else:
            lines.append(f"- Next escalation: in {self.next_in}m")
        lines.append("")
        lines.append("## Chain")
        for index, level in enumerate(self.policy.levels):
            start, end = self.policy.level_window(index)
            span = f"{start}m+" if end is None else f"{start}-{end}m"
            marker = ">" if index == self.level_index else " "
            names = ", ".join(level.targets) if level.targets else "(nobody)"
            lines.append(f"- [{marker}] Level {index + 1} ({span}): {names}")
        return "\n".join(lines) + "\n"


@dataclass
class EscalationBook:
    """Severity -> policy map with a default policy fallback."""

    policies: dict = field(default_factory=dict)
    default: str = ""

    def resolve(self, severity: str, elapsed_minutes: int) -> EscalationState:
        key = severity.strip().upper()
        policy = self.policies.get(key)
        if policy is None and self.default:
            policy = self.policies.get(self.default.upper())
        if policy is None:
            raise ValueError(
                f"no escalation policy for severity {severity!r} "
                "and no default policy configured"
            )
        return policy.state_at(elapsed_minutes)


def escalation_book_from_dict(data: dict) -> EscalationBook:
    """Build an EscalationBook from a JSON-ish dict; unknown keys are ignored."""
    policies = {}
    for raw_severity, raw_policy in data.get("policies", {}).items():
        levels = [
            EscalationLevel(
                wait_minutes=int(raw.get("wait_minutes", 0)),
                targets=list(raw.get("targets", [])),
            )
            for raw in raw_policy.get("levels", [])
        ]
        name = raw_policy.get("name", raw_severity)
        policies[raw_severity.strip().upper()] = EscalationPolicy(
            name=name, levels=levels
        )
    return EscalationBook(
        policies=policies, default=str(data.get("default", ""))
    )
