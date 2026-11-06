from datetime import datetime

from logscope.parser import parse_line, parse_lines


def test_iso_timestamp_and_level():
    entry = parse_line("2026-11-06T09:12:33Z ERROR worker failed to connect", 1)
    assert entry.timestamp == datetime(2026, 11, 6, 9, 12, 33, tzinfo=entry.timestamp.tzinfo)
    assert entry.level == "ERROR"
    assert entry.is_error


def test_space_separated_iso_timestamp():
    entry = parse_line("2026-11-06 09:12:33 INFO startup complete", 1)
    assert entry.timestamp == datetime(2026, 11, 6, 9, 12, 33)
    assert entry.level == "INFO"
    assert not entry.is_error


def test_bracketed_iso_timestamp():
    entry = parse_line("[2026-11-06 09:12:33] WARNING disk usage high", 1)
    assert entry.timestamp == datetime(2026, 11, 6, 9, 12, 33)
    assert entry.level == "WARNING"
    assert entry.is_warning


def test_syslog_timestamp_uses_current_year():
    entry = parse_line("Nov  6 09:12:33 myhost app[123]: ERROR boom", 1)
    assert entry.timestamp.month == 11
    assert entry.timestamp.day == 6
    assert entry.timestamp.hour == 9
    assert entry.level == "ERROR"


def test_warn_normalizes_to_warning():
    entry = parse_line("2026-11-06T09:12:33 WARN something odd", 1)
    assert entry.level == "WARNING"


def test_plain_line_has_no_timestamp_or_level():
    entry = parse_line("just some free text", 1)
    assert entry.timestamp is None
    assert entry.level is None
    assert entry.message == "just some free text"
    assert not entry.is_error


def test_json_line_with_message_and_level():
    entry = parse_line(
        '{"timestamp": "2026-11-06T09:12:33Z", "level": "error", "message": "db down"}', 1)
    assert entry.level == "ERROR"
    assert entry.message == "db down"
    assert entry.timestamp is not None
    assert entry.is_error


def test_json_line_with_msg_and_epoch_timestamp():
    entry = parse_line('{"time": 1794000000, "level": "info", "msg": "ok"}', 1)
    assert entry.message == "ok"
    assert entry.level == "INFO"
    assert entry.timestamp is not None


def test_json_line_without_known_keys_falls_back_to_text():
    entry = parse_line('{"foo": "bar"}', 1)
    assert entry.message == '{"foo": "bar"}'
    assert entry.level is None


def test_broken_json_falls_back_to_text():
    entry = parse_line('{"level": "error"', 1)
    assert entry.message == '{"level": "error"'
    assert entry.level == "ERROR"


def test_exception_line_sets_type_and_error_level():
    entry = parse_line("ValueError: invalid literal for int()", 1)
    assert entry.exception_type == "ValueError"
    assert entry.level == "ERROR"
    assert entry.is_error


def test_traceback_folds_into_one_entry():
    lines = [
        "2026-11-06T09:12:33 INFO starting job",
        "Traceback (most recent call last):",
        '  File "app.py", line 42, in handle',
        "    raise ValueError('bad input')",
        "ValueError: bad input",
        "2026-11-06T09:12:34 INFO job done",
    ]
    entries = parse_lines(lines)
    assert len(entries) == 3
    tb = entries[1]
    assert tb.is_traceback
    assert tb.exception_type == "ValueError"
    assert tb.message == "ValueError: bad input"
    assert tb.is_error
    assert "app.py" in tb.raw


def test_traceback_without_exception_line_still_folds():
    lines = [
        "Traceback (most recent call last):",
        '  File "app.py", line 1, in <module>',
        "2026-11-06T09:12:34 INFO recovered",
    ]
    entries = parse_lines(lines)
    assert len(entries) == 2
    assert entries[0].is_traceback
    assert entries[0].exception_type is None


def test_indented_continuation_attaches_to_previous_entry():
    lines = [
        "2026-11-06T09:12:33 ERROR something broke",
        "    caused by: missing file",
        "2026-11-06T09:12:34 INFO ok",
    ]
    entries = parse_lines(lines)
    assert len(entries) == 2
    assert "caused by" in entries[0].raw


def test_source_line_numbers_are_1_based():
    entries = parse_lines(["INFO a", "ERROR b"])
    assert entries[0].source_line == 1
    assert entries[1].source_line == 2
