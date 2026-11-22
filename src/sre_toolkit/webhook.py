"""Admission webhook audit.

A webhook configuration with no caBundle cannot be verified by the
API server at all, and one with a timeout outside the sane range
either never answers or stalls every apply it touches. This checks
a JSON list of ValidatingWebhookConfiguration and
MutatingWebhookConfiguration entries and flags the ones that cannot
be trusted, stall deploys when they fail, or have no owner, so the
webhook is fixed before it blocks the whole cluster.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WebhookConfig:
    name: str = "unnamed"
    kind: str = "validating"
    failure_policy: str = "Ignore"
    timeout_seconds: int = 10
    ca_bundle: bool = False
    namespace_selector: bool = False
    owner: str = ""


@dataclass
class WebhookResult:
    webhook: WebhookConfig
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["no caBundle"]


def check_webhooks(webhooks: list) -> list:
    results = []
    for item in webhooks:
        issues = []
        blocked = False
        if not item.ca_bundle:
            issues.append("no caBundle")
            blocked = True
        if item.timeout_seconds < 1 or item.timeout_seconds > 30:
            issues.append("timeout out of range")
            blocked = True
        if item.failure_policy not in ("Fail", "Ignore"):
            issues.append("unknown failurePolicy")
            blocked = True
        if item.failure_policy == "Fail":
            issues.append("fail-closed stalls deploys")
        if item.timeout_seconds > 10:
            issues.append("slow webhook")
        if item.kind == "mutating" and not item.namespace_selector:
            issues.append("no namespace selector")
        if not item.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(WebhookResult(item, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# Admission webhook audit", ""]
    lines.append(f"- Webhooks checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No webhooks to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Webhooks")
    lines.append(
        "| Name | Kind | Failure policy | Timeout (s) "
        "| caBundle | Owner | Verdict | Issues |"
    )
    lines.append(
        "| ---- | ---- | -------------- | ----------- "
        "| -------- | ----- | ------- | ------ |"
    )
    for result in sorted(
        results, key=lambda r: (r.webhook.kind, r.webhook.name)
    ):
        item = result.webhook
        owner = item.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {item.name} | {item.kind} | {item.failure_policy} "
            f"| {item.timeout_seconds} "
            f"| {'yes' if item.ca_bundle else 'no'} | {owner} "
            f"| {result.verdict} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def webhooks_from_json(data: list) -> list:
    return [
        WebhookConfig(
            name=item.get("name", "unnamed"),
            kind=item.get("kind", "validating"),
            failure_policy=item.get("failure_policy", "Ignore"),
            timeout_seconds=int(item.get("timeout_seconds", 10)),
            ca_bundle=bool(item.get("ca_bundle", False)),
            namespace_selector=bool(item.get("namespace_selector", False)),
            owner=item.get("owner", ""),
        )
        for item in data
    ]
