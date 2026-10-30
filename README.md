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

## Development

```bash
python -m pytest
```
