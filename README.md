# sre-toolkit

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
- [ ] Alert noise analysis: group duplicate alerts, detect flapping
- [ ] Runbook checklist runner for incidents
- [ ] On-call handoff notes generator

## Development

```bash
python -m pytest
```
