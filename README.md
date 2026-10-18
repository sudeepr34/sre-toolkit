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

## Development

```bash
python -m pytest
```
