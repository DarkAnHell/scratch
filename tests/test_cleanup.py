from __future__ import annotations

import sys

import pytest

from app import cleanup
from app import cleanup_worker, db


class DummyConfig:
    @classmethod
    def from_env(cls):
        return "config"


def test_cleanup_main_invokes_loop(monkeypatch):
    calls = {"init": 0, "run": 0}

    def fake_init_db():
        calls["init"] += 1

    def fake_run(_config):
        calls["run"] += 1
        raise SystemExit(0)

    monkeypatch.setattr(cleanup, "init_db", fake_init_db)
    monkeypatch.setattr(cleanup, "CleanupConfig", DummyConfig)
    monkeypatch.setattr(cleanup, "run_cleanup_loop", fake_run)

    with pytest.raises(SystemExit) as exc:
        cleanup.main()

    assert exc.value.code == 0
    assert calls == {"init": 1, "run": 1}


def test_cleanup_entrypoint_runs_main(monkeypatch):
    def fake_init_db():
        return None

    def fake_run(_config):
        raise SystemExit(0)

    class DummyConfig:
        @classmethod
        def from_env(cls):
            return "config"

    monkeypatch.setattr(db, "init_db", fake_init_db)
    monkeypatch.setattr(cleanup_worker, "run_cleanup_loop", fake_run)
    monkeypatch.setattr(cleanup_worker, "CleanupConfig", DummyConfig)

    sys.modules.pop("app.cleanup", None)
    with pytest.raises(SystemExit) as exc:
        __import__("runpy").run_module("app.cleanup", run_name="__main__")

    assert exc.value.code == 0
