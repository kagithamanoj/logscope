from datetime import datetime

from logscope.analyzer import analyze
from logscope.parser import parse_lines

SAMPLE = """\
2026-11-06T09:00:01Z INFO service started
2026-11-06T09:01:10Z ERROR connection to 10.0.0.5 timed out after 30s
2026-11-06T09:02:20Z ERROR connection to 10.0.0.9 timed out after 45s
2026-11-06T09:03:30Z WARNING disk usage at 91%
2026-11-06T10:00:00Z ERROR connection to 10.0.0.5 timed out after 30s
Traceback (most recent call last):
  File "app.py", line 42, in handle
    raise ValueError('bad input')
ValueError: bad input
2026-11-06T10:05:00Z INFO recovered
"""


def _entries():
    return parse_lines(SAMPLE.splitlines())


def test_totals_and_level_counts():
    summary = analyze(_entries())
    assert summary["total_lines"] == 7
    assert summary["error_count"] == 4
    assert summary["warning_count"] == 1
    assert summary["level_counts"]["INFO"] == 2
    assert summary["level_counts"]["ERROR"] == 4


def test_same_error_groups_despite_different_ips():
    summary = analyze(_entries())
    top = summary["top_errors"]
    assert top[0]["count"] == 3
    assert top[0]["signature"] == "connection to <ip> timed out after <n>"
    assert top[0]["first_seen"] == "2026-11-06T09:01:10+00:00"
    assert top[0]["last_seen"] == "2026-11-06T10:00:00+00:00"


def test_traceback_grouped_by_exception_type():
    summary = analyze(_entries())
    tb = [e for e in summary["top_errors"] if e["exception_type"] == "ValueError"]
    assert len(tb) == 1
    assert tb[0]["count"] == 1
    assert tb[0]["signature"].startswith("ValueError: ")


def test_top_limit_is_respected():
    summary = analyze(_entries(), top=1)
    assert len(summary["top_errors"]) == 1


def test_errors_by_hour_buckets():
    summary = analyze(_entries())
    assert summary["errors_by_hour"] == {
        "2026-11-06T09:00": 2,
        "2026-11-06T10:00": 1,
    }


def test_since_drops_old_timestamped_entries():
    summary = analyze(_entries(), since=datetime(2026, 11, 6, 10, 0, 0))
    assert summary["error_count"] == 2
    assert summary["lines_in_scope"] == 3


def test_since_keeps_entries_without_timestamps():
    entries = parse_lines(["ERROR undated failure"])
    summary = analyze(entries, since=datetime(2026, 11, 6, 10, 0, 0))
    assert summary["error_count"] == 1


def test_warnings_excluded_by_default_included_with_flag():
    summary = analyze(_entries())
    assert not any("disk usage" in e["signature"] for e in summary["top_errors"])
    summary = analyze(_entries(), include_warnings=True)
    assert any("disk usage" in e["signature"] for e in summary["top_errors"])


def test_empty_input_gives_empty_summary():
    summary = analyze([])
    assert summary["total_lines"] == 0
    assert summary["error_count"] == 0
    assert summary["top_errors"] == []
    assert summary["errors_by_hour"] == {}
