"""Group parsed entries into an incident-triage summary."""

from collections import Counter, defaultdict
from datetime import datetime, timezone

from .normalize import normalize_message
from .parser import LogEntry

SEVERITY = {"TRACE": 0, "DEBUG": 1, "INFO": 2, "WARNING": 3, "WARN": 3,
            "ERROR": 4, "CRITICAL": 5, "FATAL": 5}


def _signature(entry: LogEntry) -> str:
    normalized = normalize_message(entry.message)
    if entry.exception_type:
        prefix = entry.exception_type + ":"
        if normalized.startswith(prefix):
            return normalized
        return f"{entry.exception_type}: {normalized}"
    return normalized


def _as_naive_utc(value: datetime) -> datetime:
    """Compare timestamps in naive UTC terms (naive input means UTC)."""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def analyze(entries: list[LogEntry], top: int = 10,
            include_warnings: bool = False,
            since: datetime | None = None) -> dict:
    """Summarize parsed log entries for triage.

    ``since`` drops timestamped entries older than the cutoff; entries
    without a timestamp are kept because their age cannot be judged.
    """
    total_lines = len(entries)
    since_naive = _as_naive_utc(since) if since is not None else None
    kept = []
    for entry in entries:
        if since_naive is not None and entry.timestamp is not None \
                and _as_naive_utc(entry.timestamp) < since_naive:
            continue
        kept.append(entry)

    level_counts: Counter = Counter()
    for entry in kept:
        level_counts[entry.level or "UNKNOWN"] += 1

    error_count = sum(1 for e in kept if e.is_error)
    warning_count = sum(1 for e in kept if e.is_warning)

    grouped: dict[str, dict] = {}
    for entry in kept:
        if entry.is_error or (include_warnings and entry.is_warning):
            sig = _signature(entry)
            bucket = grouped.setdefault(sig, {
                "signature": sig,
                "exception_type": entry.exception_type,
                "count": 0,
                "first_seen": None,
                "last_seen": None,
                "example": entry.message,
                "example_line": entry.source_line,
            })
            bucket["count"] += 1
            if entry.timestamp is not None:
                if bucket["first_seen"] is None or entry.timestamp < bucket["first_seen"]:
                    bucket["first_seen"] = entry.timestamp
                if bucket["last_seen"] is None or entry.timestamp > bucket["last_seen"]:
                    bucket["last_seen"] = entry.timestamp

    top_errors = sorted(grouped.values(), key=lambda b: (-b["count"], b["signature"]))
    top_errors = top_errors[:top]
    for bucket in top_errors:
        bucket["first_seen"] = bucket["first_seen"].isoformat() if bucket["first_seen"] else None
        bucket["last_seen"] = bucket["last_seen"].isoformat() if bucket["last_seen"] else None

    errors_by_hour: dict[str, int] = defaultdict(int)
    for entry in kept:
        if entry.is_error and entry.timestamp is not None:
            errors_by_hour[entry.timestamp.strftime("%Y-%m-%dT%H:00")] += 1

    return {
        "total_lines": total_lines,
        "lines_in_scope": len(kept),
        "error_count": error_count,
        "warning_count": warning_count,
        "level_counts": dict(sorted(level_counts.items())),
        "top_errors": top_errors,
        "errors_by_hour": dict(sorted(errors_by_hour.items())),
    }
