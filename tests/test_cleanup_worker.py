from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app import cleanup_worker


def test_remove_expired_files_handles_missing_and_error(tmp_path, monkeypatch):
    existing = tmp_path / "old.txt"
    existing.write_text("gone", encoding="utf-8")
    missing = tmp_path / "missing.txt"

    original_unlink = Path.unlink

    def unlink_with_error(self):
        if self.name == "error.txt":
            raise OSError("boom")
        return original_unlink(self)

    error_path = tmp_path / "error.txt"
    error_path.write_text("fail", encoding="utf-8")

    monkeypatch.setattr(Path, "unlink", unlink_with_error)

    cleanup_worker.remove_expired_files(
        [
            ("tok1", str(existing)),
            ("tok2", str(missing)),
            ("tok3", str(error_path)),
        ]
    )

    assert not existing.exists()
    assert error_path.exists()


def test_run_cleanup_loop_deletes_and_sleeps(tmp_path, monkeypatch):
    data_dir = tmp_path
    expired_file = data_dir / "expired.bin"
    expired_file.write_text("bye", encoding="utf-8")

    calls = {"count": 0}

    def fake_delete_expired(_now):
        calls["count"] += 1
        if calls["count"] == 1:
            return []
        return [("tok", str(expired_file))]

    monkeypatch.setattr(cleanup_worker, "delete_expired", fake_delete_expired)
    monkeypatch.setattr(
        cleanup_worker,
        "utcnow",
        lambda: datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    def stop_sleep(_seconds):
        if calls["count"] >= 2:
            raise StopIteration

    config = cleanup_worker.CleanupConfig(data_dir=data_dir, interval_seconds=1)

    with pytest.raises(StopIteration):
        cleanup_worker.run_cleanup_loop(config, sleep=stop_sleep)

    assert not expired_file.exists()


def test_cleanup_config_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CLEAN_INTERVAL_SECONDS", "5")

    cfg = cleanup_worker.CleanupConfig.from_env()

    assert cfg.data_dir == tmp_path.resolve()
    assert cfg.interval_seconds == 5
