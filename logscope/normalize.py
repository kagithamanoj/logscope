"""Normalize log messages so the same failure collapses to one signature.

Replaces the parts that vary between occurrences of the same error:
UUIDs, IP addresses, hex values, numbers, quoted strings, and timestamps.
What is left is the shape of the message, which is what triage groups on.
"""

import re

_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_HEX_RE = re.compile(r"\b0x[0-9a-fA-F]+\b")
_LONG_HEX_RE = re.compile(r"\b[0-9a-fA-F]{16,}\b")
_ISO_TS_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b")
_QUOTED_RE = re.compile(r"""(['"])(?:(?!\1).){1,120}\1""")
_NUMBER_RE = re.compile(r"(?<![\w.])\d+(?:\.\d+)?[a-zA-Z]?\b")
_PATH_RE = re.compile(r"(?<![\w])/(?:[\w.\-]+/)+[\w.\-]*")
_WS_RE = re.compile(r"\s+")


def normalize_message(message: str) -> str:
    """Return the grouping signature for a log message."""
    text = message.strip()
    text = _UUID_RE.sub("<uuid>", text)
    text = _IPV4_RE.sub("<ip>", text)
    text = _ISO_TS_RE.sub("<ts>", text)
    text = _HEX_RE.sub("<hex>", text)
    text = _LONG_HEX_RE.sub("<hex>", text)
    text = _QUOTED_RE.sub("<str>", text)
    text = _PATH_RE.sub("<path>", text)
    text = _NUMBER_RE.sub("<n>", text)
    return _WS_RE.sub(" ", text).strip()
