"""ServiceAccount audit.

A ServiceAccount with its token auto-mounted hands every pod
that uses it a cluster credential, and one bound to
cluster-admin hands it the keys to the whole cluster. This
checks a JSON list of service accounts and flags the ones
bound to cluster-admin, running workloads as the default
account, auto-mounting tokens, or with no owner, so the
account is scoped down — or the token unmounted — before
the next compromised pod turns into a cluster takeover.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ServiceAccount:
    name: str = "unnamed"
    namespace: str = "default"
    is_default: bool = False
    automount_token: bool = True
    cluster_roles: list = field(default_factory=list)
    owner: str = ""


@dataclass
class ServiceAccountResult:
    account: ServiceAccount
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["bound to cluster-admin"]


def check_service_accounts(accounts: list) -> list:
    results = []
    for item in accounts:
        issues = []
        blocked = False
        if "cluster-admin" in item.cluster_roles:
            issues.append("bound to cluster-admin")
            blocked = True
        if item.automount_token:
            issues.append("token auto-mounted")
        if item.is_default:
            issues.append("default service account in use")
        if not item.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(ServiceAccountResult(item, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# ServiceAccount audit", ""]
    lines.append(f"- Service accounts checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No service accounts to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Service accounts")
    lines.append(
        "| Service account | Namespace | Default | Token auto-mounted "
        "| Cluster roles | Owner | Verdict | Issues |"
    )
    lines.append(
        "| ----------------- | --------- | ------- | ------------------ "
        "| ------------- | ----- | ------- | ------ |"
    )
    for result in sorted(
        results, key=lambda r: (r.account.namespace, r.account.name)
    ):
        item = result.account
        default = "yes" if item.is_default else "no"
        automount = "yes" if item.automount_token else "no"
        roles = ", ".join(item.cluster_roles) if item.cluster_roles else "—"
        owner = item.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {item.name} | {item.namespace} | {default} | {automount} "
            f"| {roles} | {owner} | {result.verdict} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def service_accounts_from_json(data: list) -> list:
    return [
        ServiceAccount(
            name=item.get("name", "unnamed"),
            namespace=item.get("namespace", "default"),
            is_default=bool(item.get("is_default", False)),
            automount_token=bool(item.get("automount_token", True)),
            cluster_roles=list(item.get("cluster_roles", [])),
            owner=item.get("owner", ""),
        )
        for item in data
    ]
