"""Triage application logs: count entries by level, surface top error messages."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

# Matches lines like: 2026-10-04 10:15:22 ERROR connection refused: db:5432
LOG_PATTERN = re.compile(
    r"(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})"
    r".*?\b(?P<level>DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL)\b"
    r"\s*[-:]*\s*(?P<msg>.*)"
)


def normalize_level(level: str) -> str:
    """Map WARN -> WARNING so counts don't split across aliases."""
    level = level.upper()
    return "WARNING" if level == "WARN" else level


def parse_line(line: str) -> dict | None:
    """Parse one log line into {level, message}; None if it doesn't match."""
    match = LOG_PATTERN.search(line)
    if not match:
        return None
    return {
        "level": normalize_level(match.group("level")),
        "message": match.group("msg").strip(),
    }


@dataclass
class LogSummary:
    total: int
    parsed: int
    by_level: dict = field(default_factory=dict)
    top_errors: list = field(default_factory=list)


def summarize(lines, top_n: int = 5) -> LogSummary:
    """Aggregate an iterable of log lines into a LogSummary."""
    by_level: Counter = Counter()
    errors: Counter = Counter()
    total = 0
    parsed = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        total += 1
        entry = parse_line(line)
        if not entry:
            continue
        parsed += 1
        by_level[entry["level"]] += 1
        if entry["level"] in ("ERROR", "CRITICAL"):
            errors[entry["message"]] += 1
    return LogSummary(
        total=total,
        parsed=parsed,
        by_level=dict(by_level),
        top_errors=errors.most_common(top_n),
    )


def error_rate(summary: LogSummary) -> float:
    """Fraction of parsed lines at ERROR or CRITICAL level."""
    if not summary.parsed:
        return 0.0
    bad = summary.by_level.get("ERROR", 0) + summary.by_level.get("CRITICAL", 0)
    return bad / summary.parsed
