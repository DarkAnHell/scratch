from __future__ import annotations

import io
import sys
from datetime import datetime, timedelta, timezone

import pytest

from app import cleanup_worker, gateway


class DummyStdin:
    def __init__(self, data: bytes):
        self.buffer = io.BytesIO(data)


class DummyStdout:
    def __init__(self):
        self.buffer = io.BytesIO()


def test_put_get_and_expire_flow(tmp_path, monkeypatch):
    store: dict[str, dict] = {}

    def insert_file(**kwargs):
        store[kwargs["token"]] = kwargs

    def get_file_by_token(token: str):
        rec = store.get(token)
        if not rec:
            return None
        return (
            rec["token"],
            rec["sha512"],
            rec["original_name"],
            rec["size_bytes"],
            rec["stored_path"],
            rec["created_at"],
            rec["expires_at"],
        )

    def delete_expired(now: datetime):
        expired = []
        for token, rec in list(store.items()):
            if rec["expires_at"] <= now:
                expired.append((token, rec["stored_path"]))
                store.pop(token)
        return expired

    monkeypatch.setattr(gateway, "insert_file", insert_file)
    monkeypatch.setattr(gateway, "get_file_by_token", get_file_by_token)
    monkeypatch.setattr(cleanup_worker, "delete_expired", delete_expired)

    created = datetime(2024, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(gateway, "utcnow", lambda: created)
    monkeypatch.setattr(cleanup_worker, "utcnow", lambda: created + timedelta(days=2))
    monkeypatch.setattr(gateway, "_token", lambda: "tok")

    # PUT (scp -t)
    payload = b"hello"
    data = b"C0644 5 hello.txt\n" + payload + b"\x00"
    stdin = DummyStdin(data)
    stdout = DummyStdout()
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stdout", stdout)
    conf = gateway.Config(data_dir=tmp_path, ttl_days=1)
    receipts = gateway.scp_receive_one(conf)

    assert receipts[0]["token"] == "tok"
    assert (tmp_path / "tok").read_bytes() == payload

    # GET (scp -f)
    stdin = DummyStdin(gateway.ACK_OK * 3)
    stdout = DummyStdout()
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    gateway.scp_send_one(conf, "tok")

    out = stdout.buffer.getvalue()
    assert payload in out

    # Expire + cleanup
    expired = cleanup_worker.delete_expired(cleanup_worker.utcnow())
    cleanup_worker.remove_expired_files(expired)

    assert not (tmp_path / "tok").exists()
    assert store == {}


def test_get_wrong_token(monkeypatch, tmp_path):
    monkeypatch.setattr(gateway, "get_file_by_token", lambda _token: None)
    monkeypatch.setattr(sys, "stderr", io.StringIO())

    with pytest.raises(SystemExit):
        gateway.scp_send_one(gateway.Config(data_dir=tmp_path, ttl_days=1), "nope")

