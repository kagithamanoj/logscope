# logscope

Mine application logs for error patterns and produce an incident-triage
summary: top exceptions, first-seen timestamps, errors by hour.

It reads the log formats you actually have: ISO 8601 and syslog-style
timestamped lines, JSON lines, and Python tracebacks. Errors that differ
only in an IP, a user id, or a timeout value collapse into one entry, so
the summary shows the failure, not every occurrence of it.

## Install

```bash
pip install logscope
```

Or from source:

```bash
pip install -e .
```

## Use

```bash
logscope app.log
logscope --top 5 --format json app.log access.log
cat app.log | logscope
logscope --since 2026-11-06T09:00:00Z app.log
```

Exit code is 0 on success and 2 on usage errors such as a missing file
or a bad `--since` timestamp.

## Example

`examples/sample.log` mixes timestamped lines, a JSON line, a
traceback, and a syslog line. Running `logscope examples/sample.log`
prints:

```
Lines scanned: 9
Errors: 6  Warnings: 1

Top errors:
  1. [3x] connection to <ip> timed out after <n>
     first seen: 2026-11-06T09:01:10+00:00 .. 2026-11-06T10:00:00+00:00
     example (line 2): connection to 10.0.0.5 timed out after 30s
  2. [1x] ValueError: bad input
     first seen: unknown time
     example (line 7): ValueError: bad input
  3. [1x] myhost app[<n>]: cache eviction failed for key user:<n>
     first seen: 2026-11-06T10:05:00
     example (line 11): myhost app[123]: cache eviction failed for key user:8842
  4. [1x] payment webhook returned <n>
     first seen: 2026-11-06T10:01:00+00:00
     example (line 6): payment webhook returned 502

Errors by hour:
  2026-11-06T09:00: 2
  2026-11-06T10:00: 3
```

The three connection timeouts are one entry because they differ only in
the IP address and the timeout value. The traceback folds into a single
`ValueError` entry with its exception line as the example.

## Options

| Flag | Meaning |
| --- | --- |
| `--top N` | How many top errors to show (default 10) |
| `--format text\|json\|markdown` | Output format (default text). Markdown is meant for pasting into an incident channel or ticket |
| `--include-warnings` | Also group WARNING entries into the top-errors list |
| `--since TIMESTAMP` | Only consider entries at or after this ISO timestamp; entries without a timestamp are always kept |

## What it parses

| Input | Handling |
| --- | --- |
| `2026-11-06T09:12:33Z ERROR ...` | ISO 8601 timestamp (with `T` or a space, optional offset), level detected |
| `[2026-11-06 09:12:33] WARNING ...` | Bracketed ISO timestamp |
| `Nov  6 09:12:33 host app[123]: ERROR ...` | Syslog-style timestamp, current year assumed |
| `{"timestamp": ..., "level": ..., "message": ...}` | JSON lines; also accepts `time`/`ts`/`@timestamp`, `severity`/`lvl`, and `msg`/`log` |
| Python tracebacks | Folded into one entry with the exception type and message |
| Anything else | Kept as an entry with no timestamp and no level, so nothing is silently dropped |

## How grouping works

Each error message is normalized before grouping: UUIDs become
`<uuid>`, IPs become `<ip>`, hex values become `<hex>`, numbers become
`<n>`, quoted strings become `<str>`, and file paths become `<path>`.
Two occurrences with the same normalized shape are the same failure.
The level word itself is stripped from the message, so `ERROR`
and `error` do not split a group.

## Library use

```python
from logscope import analyze, parse_lines

with open("app.log") as handle:
    summary = analyze(parse_lines(handle))
print(summary["top_errors"][0])
```
