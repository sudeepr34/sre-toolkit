"""Pod security-context audit.

A privileged pod — or one sharing the host network or host
PID namespace — hands a compromised container the keys to
its node, and a pod running as root with privilege escalation
allowed is one exploit away from the same. This checks a JSON
list of pods and flags the ones that are privileged, share a
host namespace, run as root, allow privilege escalation, or
write to their root filesystem, so the context is locked down
before the next container escape.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PodSecurity:
    name: str = "unnamed"
    namespace: str = "default"
    privileged: bool = False
    host_network: bool = False
    host_pid: bool = False
    run_as_root: bool = False
    allow_privilege_escalation: bool = False
    read_only_root_filesystem: bool = False
    owner: str = ""


@dataclass
class PodSecurityResult:
    pod: PodSecurity
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["privileged"]


def check_pod_security(pods: list) -> list:
    results = []
    for item in pods:
        issues = []
        blocked = False
        if item.privileged:
            issues.append("privileged")
            blocked = True
        if item.host_network:
            issues.append("host network")
            blocked = True
        if item.host_pid:
            issues.append("host PID namespace")
            blocked = True
        if item.run_as_root:
            issues.append("runs as root")
        if item.allow_privilege_escalation:
            issues.append("privilege escalation allowed")
        if not item.read_only_root_filesystem:
            issues.append("writable root filesystem")
        if not item.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(PodSecurityResult(item, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# Pod security audit", ""]
    lines.append(f"- Pods checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No pods to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Pods")
    lines.append(
        "| Pod | Namespace | Privileged | Host network | Host PID "
        "| Runs as root | Privilege escalation | Read-only rootfs "
        "| Owner | Verdict | Issues |"
    )
    lines.append(
        "| --- | --------- | ---------- | ------------ | -------- "
        "| ------------ | -------------------- | ---------------- "
        "| ----- | ------- | ------ |"
    )
    for result in sorted(
        results, key=lambda r: (r.pod.namespace, r.pod.name)
    ):
        item = result.pod
        privileged = "yes" if item.privileged else "no"
        host_network = "yes" if item.host_network else "no"
        host_pid = "yes" if item.host_pid else "no"
        root = "yes" if item.run_as_root else "no"
        escalation = "yes" if item.allow_privilege_escalation else "no"
        readonly = "yes" if item.read_only_root_filesystem else "no"
        owner = item.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {item.name} | {item.namespace} | {privileged} | "
            f"{host_network} | {host_pid} | {root} | {escalation} | "
            f"{readonly} | {owner} | {result.verdict} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def pod_security_from_json(data: list) -> list:
    return [
        PodSecurity(
            name=item.get("name", "unnamed"),
            namespace=item.get("namespace", "default"),
            privileged=bool(item.get("privileged", False)),
            host_network=bool(item.get("host_network", False)),
            host_pid=bool(item.get("host_pid", False)),
            run_as_root=bool(item.get("run_as_root", False)),
            allow_privilege_escalation=bool(
                item.get("allow_privilege_escalation", False)
            ),
            read_only_root_filesystem=bool(
                item.get("read_only_root_filesystem", False)
            ),
            owner=item.get("owner", ""),
        )
        for item in data
    ]
