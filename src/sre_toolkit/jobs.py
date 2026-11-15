"""CronJob audit.

A CronJob that never succeeded, keeps failing, or has not run in
days is a silent gap in whatever it was supposed to do — backups,
cleanup, reports. This checks a JSON list of CronJobs and flags the
ones that are broken, stale, or suspended, so the job is fixed —
or the schedule retired — before the missing run is noticed the
hard way.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CronJob:
    name: str = "unnamed"
    namespace: str = "default"
    schedule: str = ""
    last_success_hours_ago: float | None = None
    failed_runs: int = 0
    suspended: bool = False
    owner: str = ""


@dataclass
class JobResult:
    job: CronJob
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["never succeeded"]


def check_jobs(jobs: list, stale_hours: float = 24.0) -> list:
    results = []
    for job in jobs:
        issues = []
        blocked = False
        if not job.schedule:
            issues.append("no schedule")
            blocked = True
        if job.last_success_hours_ago is None:
            issues.append("never succeeded")
            blocked = True
        elif job.last_success_hours_ago > stale_hours:
            issues.append(
                f"last success {job.last_success_hours_ago:g}h ago"
            )
        if job.failed_runs >= 3:
            issues.append(f"{job.failed_runs} failed runs")
            blocked = True
        elif job.failed_runs > 0:
            issues.append(f"{job.failed_runs} failed runs")
        if job.suspended:
            issues.append("suspended")
        if not job.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(JobResult(job, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# CronJob audit", ""]
    lines.append(f"- CronJobs checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No CronJobs to check.")
        return "\n".join(lines) + "\n"
    lines.append("## CronJobs")
    lines.append("| Namespace | CronJob | Schedule | Last success | Failed | Suspended | Owner | Verdict | Issues |")
    lines.append("| --------- | ------- | -------- | ------------ | ------ | --------- | ----- | ------- | ------ |")
    for result in sorted(
        results, key=lambda r: (r.job.namespace, r.job.name)
    ):
        job = result.job
        schedule = job.schedule or "—"
        last = (
            f"{job.last_success_hours_ago:g}h ago"
            if job.last_success_hours_ago is not None
            else "never"
        )
        suspended = "yes" if job.suspended else "no"
        owner = job.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {job.namespace} | {job.name} | {schedule} | {last} "
            f"| {job.failed_runs} | {suspended} | {owner} "
            f"| {result.verdict} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def jobs_from_json(data: list) -> list:
    jobs = []
    for item in data:
        last = item.get("last_success_hours_ago")
        jobs.append(
            CronJob(
                name=item.get("name", "unnamed"),
                namespace=item.get("namespace", "default"),
                schedule=item.get("schedule", ""),
                last_success_hours_ago=None if last is None else float(last),
                failed_runs=int(item.get("failed_runs", 0)),
                suspended=bool(item.get("suspended", False)),
                owner=item.get("owner", ""),
            )
        )
    return jobs
