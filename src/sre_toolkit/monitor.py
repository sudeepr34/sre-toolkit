"""Alert rule linting.

Alert fatigue starts with sloppy rules: no severity, no runbook link,
no owner, duplicates. This lints a JSON list of alert rules and reports
every hygiene issue, so the rules that page people are the ones that
deserve to. Exit code 1 when any issue is found, for CI gating.
"""
from __future__ import annotations

from dataclasses import dataclass

VALID_SEVERITIES = ("critical", "warning", "info")


@dataclass
class AlertRule:
    name: str
    severity: str = ""
    runbook: str = ""
    owner: str = ""
    enabled: bool = True


@dataclass
class LintIssue:
    rule: str
    kind: str  # severity, runbook, owner, disabled, duplicate
    message: str


def lint_rules(rules: list) -> list:
    """Every hygiene issue found, in rule order."""
    issues = []
    seen: dict[str, int] = {}
    for rule in rules:
        seen[rule.name] = seen.get(rule.name, 0) + 1
        if not rule.enabled:
            issues.append(LintIssue(rule.name, "disabled", "rule is disabled"))
            continue
        if not rule.severity:
            issues.append(LintIssue(rule.name, "severity", "no severity set"))
        elif rule.severity.lower() not in VALID_SEVERITIES:
            issues.append(
                LintIssue(
                    rule.name, "severity",
                    f"unknown severity {rule.severity!r}",
                )
            )
        if not rule.runbook:
            issues.append(LintIssue(rule.name, "runbook", "no runbook link"))
        if not rule.owner:
            issues.append(LintIssue(rule.name, "owner", "no owner team"))
    for name, count in seen.items():
        if count > 1:
            issues.append(
                LintIssue(name, "duplicate", f"rule name appears {count} times")
            )
    return issues


def to_markdown(rules: list, issues: list) -> str:
    lines = ["# Alert rule lint", ""]
    lines.append(f"- Rules checked: {len(rules)}")
    lines.append(f"- Issues found: {len(issues)}")
    lines.append("")
    if not issues:
        lines.append("All rules clean: severity, runbook, and owner present.")
        return "\n".join(lines) + "\n"
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.kind] = counts.get(issue.kind, 0) + 1
    lines.append("## Issues by kind")
    for kind, count in sorted(counts.items()):
        lines.append(f"- {kind}: {count}")
    lines.append("")
    lines.append("## Issues")
    lines.append("| Rule | Kind | Message |")
    lines.append("| ---- | ---- | ------- |")
    for issue in issues:
        lines.append(f"| {issue.rule} | {issue.kind} | {issue.message} |")
    return "\n".join(lines) + "\n"


def rules_from_json(data: list) -> list:
    return [
        AlertRule(
            name=item.get("name", "unnamed"),
            severity=item.get("severity", ""),
            runbook=item.get("runbook", ""),
            owner=item.get("owner", ""),
            enabled=bool(item.get("enabled", True)),
        )
        for item in data
    ]
