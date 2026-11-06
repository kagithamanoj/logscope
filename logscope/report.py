"""Render a triage summary as human-readable text or Markdown."""

import json


def to_json(summary: dict) -> str:
    return json.dumps(summary, indent=2)


def to_text(summary: dict) -> str:
    lines = [
        f"Lines scanned: {summary['total_lines']}",
        f"Errors: {summary['error_count']}  Warnings: {summary['warning_count']}",
        "",
        "Top errors:",
    ]
    if not summary["top_errors"]:
        lines.append("  (none)")
    for i, err in enumerate(summary["top_errors"], start=1):
        seen = err["first_seen"] or "unknown time"
        if err["last_seen"] and err["last_seen"] != err["first_seen"]:
            seen = f"{seen} .. {err['last_seen']}"
        lines.append(f"  {i}. [{err['count']}x] {err['signature']}")
        lines.append(f"     first seen: {seen}")
        lines.append(f"     example (line {err['example_line']}): {err['example']}")
    if summary["errors_by_hour"]:
        lines.append("")
        lines.append("Errors by hour:")
        for hour, count in summary["errors_by_hour"].items():
            lines.append(f"  {hour}: {count}")
    return "\n".join(lines) + "\n"


def to_markdown(summary: dict) -> str:
    lines = [
        "## Log triage",
        "",
        f"- Lines scanned: {summary['total_lines']}",
        f"- Errors: {summary['error_count']}",
        f"- Warnings: {summary['warning_count']}",
        "",
        "### Top errors",
        "",
    ]
    if not summary["top_errors"]:
        lines.append("_No errors found._")
    else:
        lines.append("| # | Count | First seen | Last seen | Error |")
        lines.append("| --- | ---: | --- | --- | --- |")
        for i, err in enumerate(summary["top_errors"], start=1):
            sig = err["signature"].replace("|", "\\|")
            lines.append(
                f"| {i} | {err['count']} | {err['first_seen'] or '-'} | "
                f"{err['last_seen'] or '-'} | `{sig}` |"
            )
        lines.append("")
        for i, err in enumerate(summary["top_errors"], start=1):
            lines.append(f"Example for #{i} (line {err['example_line']}):")
            lines.append("")
            lines.append(f"```\n{err['example']}\n```")
            lines.append("")
    if summary["errors_by_hour"]:
        lines.append("### Errors by hour")
        lines.append("")
        for hour, count in summary["errors_by_hour"].items():
            lines.append(f"- {hour}: {count}")
    return "\n".join(lines) + "\n"
