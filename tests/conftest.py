from __future__ import annotations

import sys
import threading
import trace
import types
from pathlib import Path
from typing import Iterable

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "server"
sys.path.insert(0, str(SERVER_PATH)) if str(SERVER_PATH) not in sys.path else None

psycopg_stub = types.SimpleNamespace(connect=lambda _dsn: None)
sys.modules.setdefault("psycopg", psycopg_stub)

_TRACE: trace.Trace = trace.Trace(count=True, trace=False)
sys.settrace(_TRACE.globaltrace)
threading.settrace(_TRACE.globaltrace)


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("cov")
    group.addoption(
        "--cov",
        action="append",
        default=[],
        help="Measure coverage for specified path (custom minimal implementation).",
    )
    group.addoption(
        "--cov-report",
        action="append",
        default=[],
        help="Coverage report type (supports term, term-missing).",
    )
    group.addoption(
        "--cov-fail-under",
        type=float,
        default=0.0,
        help="Fail if total coverage is less than this value.",
    )


def _iter_cov_files(cov_targets: Iterable[str]) -> list[Path]:
    files: set[Path] = set()
    for target in cov_targets:
        target_path = Path(target)
        target_path = target_path if target_path.is_absolute() else (ROOT / target_path).resolve()
        files.update([target_path] if target_path.is_file() else [])
        for path in target_path.rglob("*.py") if target_path.is_dir() else []:
            files.add(path.resolve())
    return sorted(files)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    sys.settrace(None)
    threading.settrace(None)
    results = _TRACE.results()
    counts = results.counts

    cov_targets = session.config.getoption("cov")
    cov_report = session.config.getoption("cov_report") or []
    fail_under = float(session.config.getoption("cov_fail_under") or 0.0)

    files = _iter_cov_files(cov_targets)
    total_exec = 0
    total_hit = 0
    report_missing = any("term-missing" in r for r in cov_report)
    report_term = report_missing or any(r == "term" for r in cov_report)

    for path in files:
        exec_lines = set(trace._find_executable_linenos(str(path)).keys())
        if not exec_lines:
            continue
        hit_lines = {
            line
            for (filename, line), _count in counts.items()
            if Path(filename).resolve() == path
        }
        missing = sorted(exec_lines - hit_lines)
        total_exec += len(exec_lines)
        total_hit += len(exec_lines) - len(missing)

        missing_list = ",".join(str(n) for n in missing)
        print(f"{path}: missing lines: {missing_list}") if report_missing and missing_list else None

    total_percent = 100.0 if total_exec == 0 else (total_hit / total_exec) * 100.0
    print(f"TOTAL {total_percent:.2f}% ({total_hit}/{total_exec})") if report_term else None

    session.exitstatus = 1 if total_percent < fail_under else session.exitstatus

from app import logutil


@pytest.fixture(autouse=True)
def reset_logutil_state(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure cached log level state doesn't leak across tests.
    logutil._CURRENT_LEVEL = None
    logutil._LEVEL_SOURCE = None
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("LOG_SINK", raising=False)
    yield
    logutil._CURRENT_LEVEL = None
    logutil._LEVEL_SOURCE = None
