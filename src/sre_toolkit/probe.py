"""Endpoint probing.

The simplest health check there is: hit the endpoint and see what
comes back. Probes one or more URLs, records status code and latency,
and judges each against an expected status and a latency ceiling.
Unreachable endpoints are failures, not crashes.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class ProbeResult:
    url: str
    status_code: int  # 0 means unreachable
    latency_ms: float
    expected_status: int = 200
    max_latency_ms: float = 1000.0
    error: str = ""

    @property
    def status(self) -> str:
        return "ok" if not self.failures() else "fail"

    def failures(self) -> list:
        problems = []
        if self.status_code == 0:
            problems.append(f"unreachable ({self.error})" if self.error else "unreachable")
        elif self.status_code != self.expected_status:
            problems.append(
                f"status {self.status_code}, expected {self.expected_status}"
            )
        if self.latency_ms > self.max_latency_ms:
            problems.append(
                f"latency {self.latency_ms:.0f}ms over max {self.max_latency_ms:g}ms"
            )
        return problems


def probe_url(
    url: str,
    expected_status: int = 200,
    max_latency_ms: float = 1000.0,
    timeout: float = 5.0,
) -> ProbeResult:
    start = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            status = response.status
            response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        latency = (time.monotonic() - start) * 1000
        return ProbeResult(
            url=url, status_code=0, latency_ms=latency,
            expected_status=expected_status, max_latency_ms=max_latency_ms,
            error=str(exc),
        )
    latency = (time.monotonic() - start) * 1000
    return ProbeResult(
        url=url, status_code=status, latency_ms=latency,
        expected_status=expected_status, max_latency_ms=max_latency_ms,
    )


def to_markdown(results: list) -> str:
    lines = ["# Endpoint probes", ""]
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    summary = ", ".join(f"{n} {status}" for status, n in sorted(counts.items()))
    lines.append(f"- Probed {len(results)} endpoints: {summary}")
    lines.append("")
    lines.append("| Endpoint | Status | Latency | Detail |")
    lines.append("| -------- | ------ | ------- | ------ |")
    for result in results:
        detail = "; ".join(result.failures()) or "ok"
        lines.append(
            f"| {result.url} | {result.status_code or 'down'} "
            f"| {result.latency_ms:.0f}ms | {detail} |"
        )
    lines.append("")
    failures = [r for r in results if r.status == "fail"]
    if failures:
        lines.append("## Failures")
        for result in failures:
            lines.append(f"- {result.url}: {'; '.join(result.failures())}")
    else:
        lines.append("All endpoints healthy.")
    return "\n".join(lines) + "\n"
