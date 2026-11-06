"""Command line interface: logscope <logfile> [--top N] [--format ...]."""

import argparse
import sys
from datetime import datetime

from .analyzer import analyze
from .parser import parse_lines
from .report import to_json, to_markdown, to_text

FORMATS = ("text", "json", "markdown")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logscope",
        description="Mine application logs for error patterns and print an incident-triage summary.",
    )
    parser.add_argument("files", nargs="*", metavar="FILE",
                        help="log files to scan (reads stdin when none are given)")
    parser.add_argument("--top", type=int, default=10,
                        help="how many top errors to show (default 10)")
    parser.add_argument("--format", choices=FORMATS, default="text",
                        help="output format: text, json, or markdown (default text)")
    parser.add_argument("--include-warnings", action="store_true",
                        help="also group WARNING entries into the top-errors list")
    parser.add_argument("--since", metavar="TIMESTAMP",
                        help="only consider entries at or after this ISO timestamp; "
                             "entries without a timestamp are always kept")
    return parser


def _read_inputs(files: list[str]) -> list[str] | None:
    lines: list[str] = []
    if not files:
        lines.extend(sys.stdin)
        return lines
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                lines.extend(handle)
        except OSError as exc:
            print(f"logscope: cannot read {path}: {exc}", file=sys.stderr)
            return None
    return lines


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.top < 1:
        print("logscope: --top must be at least 1", file=sys.stderr)
        return 2
    since = None
    if args.since:
        try:
            since = datetime.fromisoformat(args.since.replace("Z", "+00:00"))
        except ValueError:
            print(f"logscope: --since is not a valid ISO timestamp: {args.since}",
                  file=sys.stderr)
            return 2
    lines = _read_inputs(args.files)
    if lines is None:
        return 2
    entries = parse_lines(lines)
    summary = analyze(entries, top=args.top,
                      include_warnings=args.include_warnings, since=since)
    if args.format == "json":
        print(to_json(summary))
    elif args.format == "markdown":
        print(to_markdown(summary), end="")
    else:
        print(to_text(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
