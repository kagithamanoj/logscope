"""logscope: mine application logs for error patterns and produce an
incident-triage summary (top exceptions, first-seen timestamps)."""

from .analyzer import analyze
from .parser import LogEntry, parse_lines

__all__ = ["analyze", "LogEntry", "parse_lines"]
__version__ = "0.1.0"
