"""Parse log lines into structured entries.

Handles three shapes found in real application logs:

* JSON lines: ``{"timestamp": ..., "level": ..., "message": ...}``
* Timestamped text lines: ISO 8601 or syslog-style ``Nov  6 09:12:33``
* Python tracebacks, folded into a single entry carrying the exception
  type and message.

Lines that match none of these still become entries with no timestamp and
no level, so nothing is silently dropped.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime

LEVELS = ("TRACE", "DEBUG", "INFO", "WARNING", "WARN", "ERROR", "CRITICAL", "FATAL")

_ISO_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?"
    r"(?:Z|[+-]\d{2}:?\d{2})?)"
)
_BRACKETED_ISO_RE = re.compile(
    r"^\[(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?"
    r"(?:Z|[+-]\d{2}:?\d{2})?)\]"
)
_SYSLOG_RE = re.compile(
    r"^(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"(?P<day>\d{1,2}) (?P<time>\d{2}:\d{2}:\d{2})"
)
_LEVEL_RE = re.compile(r"\b(TRACE|DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\b", re.IGNORECASE)
_EXCEPTION_RE = re.compile(r"^(?P<type>[\w.]+(?:Error|Exception|Warning|Timeout|Failure|Interrupt|SystemExit))\s*:\s*(?P<msg>.*)$")
_TRACEBACK_START = "Traceback (most recent call last):"

_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


@dataclass
class LogEntry:
    """One parsed log line (or one folded traceback block)."""

    raw: str
    timestamp: datetime | None = None
    level: str | None = None
    message: str = ""
    source_line: int = 0
    is_traceback: bool = False
    exception_type: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def is_error(self) -> bool:
        if self.is_traceback or self.exception_type:
            return True
        return self.level in ("ERROR", "CRITICAL", "FATAL")

    @property
    def is_warning(self) -> bool:
        return self.level in ("WARNING", "WARN")


def _parse_iso(text: str) -> datetime | None:
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_syslog(match: re.Match) -> datetime:
    now = datetime.now()
    return datetime(
        now.year,
        _MONTHS[match.group("mon")],
        int(match.group("day")),
        *map(int, match.group("time").split(":")),
    )


def _level_of(text: str) -> str | None:
    match = _LEVEL_RE.search(text)
    if not match:
        return None
    level = match.group(1).upper()
    return "WARNING" if level == "WARN" else level


def _json_entry(obj: dict, raw: str, lineno: int) -> LogEntry | None:
    message = None
    for key in ("message", "msg", "log", "event"):
        if isinstance(obj.get(key), str):
            message = obj[key]
            break
    level = None
    for key in ("level", "severity", "lvl"):
        if isinstance(obj.get(key), str):
            level = obj[key].upper()
            break
    timestamp = None
    for key in ("timestamp", "time", "ts", "@timestamp"):
        value = obj.get(key)
        if isinstance(value, str):
            timestamp = _parse_iso(value)
            if timestamp:
                break
        elif isinstance(value, (int, float)):
            try:
                timestamp = datetime.fromtimestamp(value)
                break
            except (ValueError, OSError, OverflowError):
                continue
    if message is None and level is None and timestamp is None:
        return None
    if level is not None and level not in LEVELS:
        level = None
    return LogEntry(
        raw=raw,
        timestamp=timestamp,
        level=level,
        message=message or raw,
        source_line=lineno,
        extra={k: v for k, v in obj.items() if k not in ("message", "msg", "log", "event", "level", "severity", "lvl", "timestamp", "time", "ts", "@timestamp")},
    )


def parse_line(line: str, lineno: int = 0) -> LogEntry:
    """Parse one log line into a LogEntry."""
    raw = line.rstrip("\n")
    stripped = raw.strip()

    if stripped.startswith("{"):
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            obj = None
        if isinstance(obj, dict):
            entry = _json_entry(obj, raw, lineno)
            if entry is not None:
                return entry

    rest = raw
    timestamp = None
    for pattern, parser in (
        (_BRACKETED_ISO_RE, lambda m: _parse_iso(m.group("ts"))),
        (_ISO_RE, lambda m: _parse_iso(m.group("ts"))),
        (_SYSLOG_RE, _parse_syslog),
    ):
        match = pattern.match(raw)
        if match:
            timestamp = parser(match)
            rest = raw[match.end():].strip()
            break

    level = _level_of(rest)
    if level is not None:
        # Drop the level token itself so it does not pollute the message
        # or the grouping signature. A quoted word is a data value, not
        # a level marker, so leave it alone.
        match = _LEVEL_RE.search(rest)
        if match and (match.start() == 0 or rest[match.start() - 1] not in "\"'"):
            rest = (rest[:match.start()] + rest[match.end():]).strip()
            rest = re.sub(r"^[:\-]\s*", "", rest)
            rest = " ".join(rest.split())
    message = rest
    exception_type = None
    exc = _EXCEPTION_RE.match(rest)
    if exc:
        exception_type = exc.group("type")
        message = rest
        if level is None:
            level = "ERROR"
    return LogEntry(
        raw=raw,
        timestamp=timestamp,
        level=level,
        message=message,
        source_line=lineno,
        exception_type=exception_type,
    )


def parse_lines(lines) -> list[LogEntry]:
    """Parse an iterable of log lines, folding tracebacks into one entry."""
    entries: list[LogEntry] = []
    current_tb: list[str] | None = None
    tb_start = 0

    def flush_traceback():
        nonlocal current_tb
        if not current_tb:
            return
        block = current_tb
        current_tb = None
        last = block[-1].strip()
        exc = _EXCEPTION_RE.match(last)
        exception_type = exc.group("type") if exc else None
        message = last if exc else "Traceback (no exception line captured)"
        timestamp = None
        level = None
        first = parse_line(block[0], tb_start)
        timestamp, level = first.timestamp, first.level
        entries.append(LogEntry(
            raw="\n".join(block),
            timestamp=timestamp,
            level=level or "ERROR",
            message=message,
            source_line=tb_start,
            is_traceback=True,
            exception_type=exception_type,
        ))

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if current_tb is not None:
            if line.startswith((" ", "\t")) or not stripped:
                current_tb.append(line.rstrip("\n"))
                continue
            if _EXCEPTION_RE.match(stripped):
                # The exception line ends the traceback block.
                current_tb.append(line.rstrip("\n"))
                flush_traceback()
                continue
            flush_traceback()
            # Fall through: process this line normally.
        if stripped == _TRACEBACK_START:
            current_tb = [line.rstrip("\n")]
            tb_start = lineno
            continue
        entry = parse_line(line, lineno)
        # Indented continuation lines belong to the previous entry.
        if stripped and line[:1] in (" ", "\t") and entries:
            entries[-1].raw += "\n" + line.rstrip("\n")
            continue
        entries.append(entry)
    flush_traceback()
    return entries
