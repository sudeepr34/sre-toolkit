"""DNS resolution checks.

Before blaming the service, check the name resolves. This resolves
each hostname to its IPv4 addresses and reports which names fail, so a
DNS outage is caught by the checker instead of by the first customer.
"""
from __future__ import annotations

import socket
from dataclasses import dataclass


@dataclass
class DNSResult:
    host: str
    addresses: list
    error: str = ""  # "" when the lookup succeeded

    @property
    def ok(self) -> bool:
        return not self.error


def resolve_host(host: str) -> DNSResult:
    try:
        infos = socket.getaddrinfo(
            host, None, socket.AF_INET, socket.SOCK_STREAM
        )
    except (socket.gaierror, UnicodeError) as exc:
        return DNSResult(host, [], str(exc))
    addresses = sorted({info[4][0] for info in infos})
    return DNSResult(host, addresses)


def check_dns(hosts: list) -> list:
    return [resolve_host(host) for host in hosts]


def to_markdown(results: list) -> str:
    lines = ["# DNS resolution check", ""]
    lines.append(f"- Hosts checked: {len(results)}")
    lines.append(f"- Resolved: {sum(1 for r in results if r.ok)}")
    lines.append(f"- Failed: {sum(1 for r in results if not r.ok)}")
    lines.append("")
    if not results:
        lines.append("No hosts to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Hosts")
    lines.append("| Host | Addresses | Status |")
    lines.append("| ---- | --------- | ------ |")
    for result in results:
        if result.ok:
            lines.append(
                f"| {result.host} | {', '.join(result.addresses)} | ok |"
            )
        else:
            lines.append(f"| {result.host} | — | failed: {result.error} |")
    return "\n".join(lines) + "\n"
