from __future__ import annotations

import io

from app import logutil


def test_logutil_writes_to_stderr_when_no_sink(monkeypatch):
    buffer = io.StringIO()
    monkeypatch.setattr(logutil, "sys", type("Sys", (), {"stderr": buffer}))
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    logutil.info("hello")

    output = buffer.getvalue()
    assert "INFO" in output
    assert "hello" in output


def test_logutil_writes_to_file_sink(tmp_path, monkeypatch):
    sink = tmp_path / "log.txt"
    monkeypatch.setenv("LOG_SINK", str(sink))
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    logutil.debug("file sink")

    data = sink.read_text(encoding="utf-8")
    assert "DEBUG" in data
    assert "file sink" in data


def test_logutil_invalid_level_emits_warning(tmp_path, monkeypatch):
    sink = tmp_path / "log.txt"
    monkeypatch.setenv("LOG_SINK", str(sink))
    monkeypatch.setenv("LOG_LEVEL", "NOPE")

    logutil.info("noop")

    data = sink.read_text(encoding="utf-8")
    assert "unknown log level" in data


def test_logutil_sink_fallback_to_stderr(monkeypatch, tmp_path):
    # Use a directory path to force open() failure and fall back to stderr.
    sink_dir = tmp_path / "sink"
    sink_dir.mkdir()
    buffer = io.StringIO()
    monkeypatch.setattr(logutil, "sys", type("Sys", (), {"stderr": buffer}))
    monkeypatch.setenv("LOG_SINK", str(sink_dir))
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    logutil.info("fallback")

    output = buffer.getvalue()
    assert "fallback" in output


def test_logutil_explicit_stderr_sink(monkeypatch):
    buffer = io.StringIO()
    monkeypatch.setattr(logutil, "sys", type("Sys", (), {"stderr": buffer}))
    monkeypatch.setenv("LOG_SINK", "stderr")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    logutil.info("explicit")

    output = buffer.getvalue()
    assert "explicit" in output


def test_logutil_alias_level(monkeypatch):
    buffer = io.StringIO()
    monkeypatch.setattr(logutil, "sys", type("Sys", (), {"stderr": buffer}))
    monkeypatch.setenv("LOG_LEVEL", "WARN")

    logutil.log("warn", "alias")

    output = buffer.getvalue()
    assert "WARNING" in output
    assert "alias" in output


def test_logutil_wrappers(monkeypatch):
    buffer = io.StringIO()
    monkeypatch.setattr(logutil, "sys", type("Sys", (), {"stderr": buffer}))
    monkeypatch.setenv("LOG_LEVEL", "VERBOSE")

    logutil.error("err")
    logutil.warning("warn")
    logutil.verbose("verb")

    output = buffer.getvalue()
    assert "ERROR" in output
    assert "WARNING" in output
    assert "VERBOSE" in output
