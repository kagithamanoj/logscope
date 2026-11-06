import json

import pytest

from logscope.cli import main
from logscope.report import to_markdown, to_text

SAMPLE = """\
2026-11-06T09:01:10Z ERROR connection to 10.0.0.5 timed out after 30s
2026-11-06T09:02:20Z ERROR connection to 10.0.0.9 timed out after 45s
2026-11-06T09:03:30Z WARNING disk usage at 91%
"""


def _write_sample(tmp_path):
    path = tmp_path / "app.log"
    path.write_text(SAMPLE)
    return str(path)


def test_cli_text_output(tmp_path, capsys):
    assert main([_write_sample(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Errors: 2" in out
    assert "connection to <ip> timed out after <n>" in out
    assert "[2x]" in out


def test_cli_json_output(tmp_path, capsys):
    assert main([_write_sample(tmp_path), "--format", "json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["error_count"] == 2
    assert summary["top_errors"][0]["count"] == 2
    assert summary["top_errors"][0]["first_seen"] == "2026-11-06T09:01:10+00:00"


def test_cli_markdown_output(tmp_path, capsys):
    assert main([_write_sample(tmp_path), "--format", "markdown"]) == 0
    out = capsys.readouterr().out
    assert "## Log triage" in out
    assert "| 1 | 2 |" in out


def test_cli_top_flag_limits_output(tmp_path, capsys):
    assert main([_write_sample(tmp_path), "--top", "1"]) == 0
    out = capsys.readouterr().out
    assert "1. [2x]" in out
    assert "2." not in out


def test_cli_missing_file_exits_2(tmp_path, capsys):
    assert main([str(tmp_path / "nope.log")]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_cli_bad_since_exits_2(tmp_path, capsys):
    assert main([_write_sample(tmp_path), "--since", "not-a-date"]) == 2
    assert "--since" in capsys.readouterr().err


def test_cli_top_zero_exits_2(tmp_path, capsys):
    assert main([_write_sample(tmp_path), "--top", "0"]) == 2


def test_cli_reads_stdin_when_no_file(monkeypatch, capsys):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO(SAMPLE))
    assert main([]) == 0
    assert "Errors: 2" in capsys.readouterr().out


def test_text_report_with_no_errors():
    summary = {
        "total_lines": 2, "error_count": 0, "warning_count": 0,
        "top_errors": [], "errors_by_hour": {},
    }
    assert "(none)" in to_text(summary)
    assert "_No errors found._" in to_markdown(summary)


def test_cli_multiple_files(tmp_path, capsys):
    first = tmp_path / "a.log"
    second = tmp_path / "b.log"
    first.write_text("2026-11-06T09:01:10Z ERROR one failed\n")
    second.write_text("2026-11-06T09:02:10Z ERROR two failed\n")
    assert main([str(first), str(second)]) == 0
    assert "Errors: 2" in capsys.readouterr().out
