"""RBAC binding audit.

A cluster-admin binding handed to the wrong service account is
a quiet privilege escalation waiting for an incident. This
checks a JSON list of role bindings and flags the ones that
grant cluster-admin, wildcard verbs or resources, or belong
to a service account with no owner, so the binding is scoped
down — or removed — before it is abused.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RoleBinding:
    name: str = "unnamed"
    namespace: str = "default"
    subject_kind: str = ""
    subject_name: str = ""
    role: str = ""
    verbs: list = field(default_factory=list)
    resources: list = field(default_factory=list)
    owner: str = ""


@dataclass
class RbacResult:
    binding: RoleBinding
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["cluster-admin role"]


def check_bindings(bindings: list) -> list:
    results = []
    for binding in bindings:
        issues = []
        blocked = False
        if binding.role == "cluster-admin":
            issues.append("cluster-admin role")
            blocked = True
        if "*" in binding.verbs:
            issues.append("wildcard verb")
            blocked = True
        if "*" in binding.resources:
            issues.append("wildcard resource")
        if (
            binding.subject_kind == "ServiceAccount"
            and not binding.owner
        ):
            issues.append("service account with no owner")
        elif not binding.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(RbacResult(binding, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# RBAC binding audit", ""]
    lines.append(f"- Bindings checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No bindings to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Bindings")
    lines.append(
        "| Namespace | Binding | Subject | Role | Owner | Verdict | Issues |"
    )
    lines.append(
        "| --------- | ------- | ------- | ---- | ----- | ------- | ------ |"
    )
    for result in sorted(
        results, key=lambda r: (r.binding.namespace, r.binding.name)
    ):
        binding = result.binding
        subject = (
            f"{binding.subject_kind}:{binding.subject_name}"
            if binding.subject_kind
            else binding.subject_name or "—"
        )
        owner = binding.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {binding.namespace} | {binding.name} | {subject} | "
            f"{binding.role or '—'} | {owner} | {result.verdict} "
            f"| {issues} |"
        )
    return "\n".join(lines) + "\n"


def bindings_from_json(data: list) -> list:
    return [
        RoleBinding(
            name=item.get("name", "unnamed"),
            namespace=item.get("namespace", "default"),
            subject_kind=item.get("subject_kind", ""),
            subject_name=item.get("subject_name", ""),
            role=item.get("role", ""),
            verbs=list(item.get("verbs", [])),
            resources=list(item.get("resources", [])),
            owner=item.get("owner", ""),
        )
        for item in data
    ]
