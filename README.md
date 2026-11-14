# sre-toolkit

[![CI](https://github.com/sudeepr34/sre-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/sudeepr34/sre-toolkit/actions/workflows/ci.yml)

A Python CLI toolkit for SRE / on-call workflows. Small, dependency-free utilities
for the things on-call engineers do every day: triage logs, cut alert noise,
and run incidents from checklists instead of memory.

## Install

```bash
pip install -e .
```

## Usage

```bash
# Summarize a log file: counts by level, error rate, top error messages
sre-toolkit logs /var/log/app.log --top 10

# Analyze alert noise from a JSON alert dump: duplicates, flapping
sre-toolkit alerts alerts.json --top 5

# Generate on-call handoff notes (empty template, or from a JSON file)
sre-toolkit handoff --shift 2026-10-12 --outgoing priya --incoming sudeep
sre-toolkit handoff --file handoff.json

# Start-of-shift brief: alert noise + carryover from the last handoff
sre-toolkit brief alerts.json --handoff handoff.json --shift 2026-10-13

# Blameless postmortem from an incident timeline (empty template, or from a JSON file)
sre-toolkit postmortem --title "db outage" --severity SEV-1
sre-toolkit postmortem --file incident.json

# SLO burn-rate assessment: page/ticket/watch severity from error budget math
sre-toolkit slo --target 99.9 --error-rate 0.5 --window-hours 720
sre-toolkit slo --file slo.json --elapsed-hours 168

# Change-freeze gate: exit 0 when deploys are allowed, 1 when blocked
sre-toolkit deploy --freezes freezes.json
sre-toolkit deploy --freezes freezes.json --now 2026-10-19T12:00

# Status-page draft: customer-facing incident updates in Markdown
sre-toolkit comms --title "checkout api errors" --status identified --severity SEV-2
sre-toolkit comms --file status.json --message "Rollback complete, monitoring." --now 2026-10-19T10:30

# Escalation resolution: who to page now, given severity + elapsed incident time
sre-toolkit escalate policy.json --severity SEV-1 --elapsed 12

# On-call lookup: who's holding the pager, shift window, who's next
sre-toolkit oncall rota.json --date 2026-10-21

# Weekly ops review: roll up postmortem JSON files into a review summary
sre-toolkit review --week 2026-W42 incident1.json incident2.json

# Live incident tracking: start, status, notes, list, resolve
sre-toolkit incident start --title "db outage" --severity SEV-1
sre-toolkit incident status INC-0001
sre-toolkit incident note INC-0001 --message "Rollback started."
sre-toolkit incident resolve INC-0001

# Capacity planning: project growth against capacity, find the breach period
sre-toolkit capacity forecast --current-load 600 --capacity 1000 --growth 0.10

# Game-day drills: scenario plans and run sheets
sre-toolkit drill list
sre-toolkit drill show db-failover
sre-toolkit drill run db-failover

# Backup verification: stale backups and untested restores
sre-toolkit backup check --backups backups.json

# Cost attribution: top spenders, month-over-month, over-budget alerts
sre-toolkit cost report --costs costs.json --budgets budgets.json --month 2026-10 --prev-month 2026-09

# Toil tracking: where the time goes, share of capacity, automation candidates
sre-toolkit toil report --toil toil.json --capacity-minutes 9600

# Dependency graph: blast radius and cycle detection
sre-toolkit deps report --graph graph.json --service db

# Alert rule lint: severity, runbook, owner, duplicates (exit 1 on issues)
sre-toolkit monitor lint --rules rules.json

# Config drift: expected vs actual, dotted paths (exit 1 on drift)
sre-toolkit audit diff --expected expected.json --actual actual.json

# Retention policy: shortfalls and unconfigured retention (exit 1 on gaps)
sre-toolkit retention check --retention retention.json

# Queue backlog: depth and age breaches (exit 1 on breach)
sre-toolkit queue check --queues queues.json

# Rollout progress: stuck past deadline or failed (exit 1 on problems)
sre-toolkit rollout check --rollouts rollouts.json

# Canary analysis: promote / hold / rollback (exit 0 only on promote)
sre-toolkit canary analyze --canary-error-rate 0.011 --baseline-error-rate 0.010 --canary-p99 220 --baseline-p99 200 --canary-requests 500

# Endpoint probing: status + latency checks (exit 1 on failure)
sre-toolkit probe check https://api.example.com/health

# Service health rollup: worst status wins (exit 1 unless all up)
sre-toolkit health rollup --checks checks.json

# Service catalog audit: owner, tier, runbook (exit 1 on issues)
sre-toolkit service audit --services services.json

# DORA metrics: deployment frequency + change failure rate
sre-toolkit dora report --deploys deploys.json --since 2026-10-01 --until 2026-10-31

# Latency percentiles: p50/p95/p99 with a p95 breach gate
sre-toolkit latency analyze --samples samples.json --p95-threshold 500

# TLS certificate expiry: warn / critical / expired
sre-toolkit cert check --certs certs.json

# Distributed trace analysis: critical path + error spans
sre-toolkit trace analyze --spans spans.json

# Feature flag audit: stale enabled flags + missing owners
sre-toolkit flags audit --flags flags.json

# DNS resolution: which hostnames resolve, which fail
sre-toolkit dns check api.example.com db.example.com

# SLA availability: uptime vs target, error budget left in minutes
sre-toolkit sla check --sla sla.json

# Secrets rotation audit: overdue / due soon / unknown (metadata only)
sre-toolkit secrets audit --secrets secrets.json

# Rollback readiness: previous version, runbook, tested rollback
sre-toolkit rollback check --deploys deploys.json

# Event correlation: bursts per service + windows where services fire together
sre-toolkit events correlate --events events.json

# Change collision detection: overlapping changes on the same service
sre-toolkit change check --changes changes.json

# Vulnerability triage: overdue / due-soon findings vs severity SLAs
sre-toolkit vuln triage --findings findings.json

# On-call coverage: uncovered days in a date range
sre-toolkit schedule coverage --shifts shifts.json --since 2026-11-01 --until 2026-11-30

# Maintenance window check: conflicts with change freezes
sre-toolkit maintenance check --service api --start 2026-11-28T02:00:00 --end 2026-11-28T04:00:00 --freezes freezes.json

# Pod restart analysis: crash-looping pods by restart count
sre-toolkit pods check --pods pods.json

# Host inventory audit: missing owners, unknown environments, stale patches
sre-toolkit inventory audit --hosts hosts.json

# Release cadence: days since the last release per service
sre-toolkit releases cadence --releases releases.json

# Migration status: pending, failed, and stale-pending migrations
sre-toolkit migrations status --migrations migrations.json

# Cluster node health: not-ready and over-committed nodes
sre-toolkit nodes health --nodes nodes.json

# Replica count audit: under-replicated and down deployments
sre-toolkit replicas audit --deployments deployments.json

# Namespace resource quota check: namespaces near their quotas
sre-toolkit quota check --namespaces namespaces.json

# Persistent volume usage: near-full and full volumes
sre-toolkit pvc usage --volumes volumes.json

# NetworkPolicy audit: unsegmented workloads and allow-all rules
sre-toolkit network audit --workloads workloads.json
```

Example output:

```
lines: 1240 (parsed 1198)
by level:
  ERROR: 37
  INFO: 1102
  WARNING: 59
error rate: 3.1%
top errors:
  [21x] connection refused: postgres-primary:5432
  [9x] upstream timeout after 30s: /api/checkout
```

## Roadmap

- [x] Log triage (`logs` command)
- [x] Alert noise analysis: group duplicate alerts, detect flapping (`alerts` command)
- [x] Runbook checklist runner for incidents (`runbook` command)
- [x] On-call handoff notes generator (`handoff` command)
- [x] Start-of-shift brief: alert noise + carryover (`brief` command)
- [x] Blameless postmortem generator with timeline milestones (`postmortem` command)
- [x] SLO burn-rate and error-budget assessment (`slo` command)
- [x] Change-freeze gate for deployments (`deploy` command)
- [x] Status-page update drafter for incidents (`comms` command)
- [x] Escalation policy resolution: who to page now (`escalate` command)
- [x] On-call rotation lookup: who's holding the pager (`oncall` command)
- [x] Weekly ops review rollup from postmortems (`review` command)
- [x] Live incident tracking: start/status/note/list/resolve (`incident` command)
- [x] Capacity planning: growth projection + scale timing (`capacity` command)
- [x] Game-day drills: scenario library + run sheets (`drill` command)
- [x] Backup verification: stale backups + restore-test staleness (`backup` command)
- [x] Cost attribution: top spenders, MoM change, over-budget alerts (`cost` command)
- [x] Toil tracking: time by task/category, share of capacity, automation candidates (`toil` command)
- [x] Dependency graph: blast radius + cycle detection (`deps` command)
- [x] Alert rule lint: severity, runbook, owner, duplicates (`monitor` command)
- [x] Config drift: changed/missing/extra keys with dotted paths (`audit` command)
- [x] Retention policy: shortfalls + unconfigured retention (`retention` command)
- [x] Queue backlog: depth + age breaches (`queue` command)
- [x] Rollout progress: stuck past deadline or failed (`rollout` command)
- [x] Canary analysis: promote / hold / rollback verdict (`canary` command)
- [x] Endpoint probing: status + latency checks (`probe` command)
- [x] Service health rollup: worst status wins (`health` command)
- [x] Service catalog audit: owner, tier, runbook (`service` command)
- [x] DORA metrics: deployment frequency + change failure rate (`dora` command)
- [x] Latency percentiles: p50/p95/p99 with a p95 breach gate (`latency` command)
- [x] TLS certificate expiry: warn / critical / expired (`cert` command)
- [x] Distributed trace analysis: critical path + error spans (`trace` command)
- [x] Feature flag audit: stale enabled flags + missing owners (`flags` command)
- [x] DNS resolution: which hostnames resolve, which fail (`dns` command)
- [x] SLA availability: uptime vs target, error budget left in minutes (`sla` command)
- [x] Secrets rotation audit: overdue / due soon / unknown (`secrets` command)
- [x] Rollback readiness: previous version, runbook, tested rollback (`rollback` command)
- [x] Event correlation: bursts per service + windows where services fire together (`events` command)
- [x] Change collision detection: overlapping changes on the same service (`change` command)
- [x] Vulnerability triage: overdue / due-soon findings vs severity SLAs (`vuln` command)
- [x] On-call coverage: uncovered days in a date range (`schedule` command)
- [x] Maintenance window check: conflicts with change freezes (`maintenance` command)
- [x] Pod restart analysis: crash-looping pods by restart count (`pods` command)
- [x] Host inventory audit: missing owners, unknown environments, stale patches (`inventory` command)
- [x] Release cadence: days since the last release per service (`releases` command)
- [x] Migration status: pending, failed, and stale-pending migrations (`migrations` command)
- [x] Cluster node health: not-ready and over-committed nodes (`nodes` command)
- [x] Replica count audit: under-replicated and down deployments (`replicas` command)
- [x] Namespace resource quota check: namespaces near their quotas (`quota` command)
- [x] Persistent volume usage: near-full and full volumes (`pvc` command)
- [x] NetworkPolicy audit: unsegmented workloads and allow-all rules (`network` command)

## Development

```bash
python -m pytest
```
