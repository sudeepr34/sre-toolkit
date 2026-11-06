"""Distributed trace analysis.

When a request is slow, the question is where the time went. This
analyzes a list of spans (one trace) and finds the total duration, the
slowest span, the critical path — the longest root-to-leaf chain — and
any error spans, so the slow part of the call graph is named, not guessed.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_id: str  # "" for the root span
    service: str
    operation: str
    start_ms: float = 0.0
    duration_ms: float = 0.0
    status: str = "ok"  # ok, error


def total_duration_ms(spans: list) -> float:
    """Wall-clock span of the trace: latest end minus earliest start."""
    if not spans:
        return 0.0
    start = min(span.start_ms for span in spans)
    end = max(span.start_ms + span.duration_ms for span in spans)
    return end - start


def slowest_span(spans: list) -> Span | None:
    if not spans:
        return None
    return max(spans, key=lambda span: span.duration_ms)


def error_spans(spans: list) -> list:
    return [span for span in spans if span.status.lower() == "error"]


def critical_path(spans: list) -> list:
    """Longest root-to-leaf chain by summed duration.

    Returns the spans along that path, root first. Spans whose parent
    is missing are treated as additional roots.
    """
    if not spans:
        return []
    by_parent: dict[str, list] = {}
    for span in spans:
        by_parent.setdefault(span.parent_id, []).append(span)
    span_ids = {span.span_id for span in spans}
    roots = [span for span in spans if not span.parent_id or span.parent_id not in span_ids]

    def longest_from(span: Span) -> list:
        children = by_parent.get(span.span_id, [])
        if not children:
            return [span]
        best = max((longest_from(child) for child in children), key=_path_duration)
        return [span, *best]

    return max((longest_from(root) for root in roots), key=_path_duration)


def _path_duration(path: list) -> float:
    return sum(span.duration_ms for span in path)


def to_markdown(spans: list) -> str:
    lines = ["# Trace analysis", ""]
    lines.append(f"- Spans: {len(spans)}")
    lines.append(f"- Total duration: {total_duration_ms(spans):.1f} ms")
    lines.append(f"- Error spans: {len(error_spans(spans))}")
    lines.append("")
    slowest = slowest_span(spans)
    if slowest is not None:
        lines.append(
            f"- Slowest span: {slowest.service}::{slowest.operation} "
            f"({slowest.duration_ms:.1f} ms)"
        )
    path = critical_path(spans)
    if path:
        lines.append(f"- Critical path: {_path_duration(path):.1f} ms")
        lines.append("")
        lines.append("## Critical path")
        for span in path:
            lines.append(
                f"- {span.service}::{span.operation} ({span.duration_ms:.1f} ms)"
            )
    errors = error_spans(spans)
    if errors:
        lines.append("")
        lines.append("## Error spans")
        for span in errors:
            lines.append(f"- {span.service}::{span.operation} ({span.span_id})")
    return "\n".join(lines) + "\n"


def spans_from_json(data: list) -> list:
    return [
        Span(
            trace_id=item.get("trace_id", ""),
            span_id=item.get("span_id", ""),
            parent_id=item.get("parent_id", ""),
            service=item.get("service", "unnamed"),
            operation=item.get("operation", "unnamed"),
            start_ms=float(item.get("start_ms", 0.0)),
            duration_ms=float(item.get("duration_ms", 0.0)),
            status=item.get("status", "ok"),
        )
        for item in data
    ]
