"""Command line interface for sre-toolkit."""
from __future__ import annotations

import argparse
import sys

from .log_triage import error_rate, summarize


def cmd_logs(args: argparse.Namespace) -> int:
    with open(args.file) as handle:
        summary = summarize(handle, top_n=args.top)
    print(f"lines: {summary.total} (parsed {summary.parsed})")
    print("by level:")
    for level, count in sorted(summary.by_level.items()):
        print(f"  {level}: {count}")
    print(f"error rate: {error_rate(summary):.1%}")
    if summary.top_errors:
        print("top errors:")
        for message, count in summary.top_errors:
            print(f"  [{count}x] {message[:120]}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sre-toolkit", description="Small CLI utilities for on-call SRE work."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    logs = sub.add_parser("logs", help="Triage a log file.")
    logs.add_argument("file", help="Path to the log file.")
    logs.add_argument("--top", type=int, default=5, help="Top error messages to show.")
    logs.set_defaults(func=cmd_logs)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
