from __future__ import annotations

import hashlib
import io
import sys
from datetime import datetime, timedelta, timezone

import pytest

from app import gateway


class DummyStdin:
    def __init__(self, data: bytes):
        self.buffer = io.BytesIO(data)


class DummyStdout:
    def __init__(self):
        self.buffer = io.BytesIO()


def _set_io(monkeypatch, data: bytes) -> DummyStdout:
    stdin = DummyStdin(data)
    stdout = DummyStdout()
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stdout", stdout)
    return stdout


def test_scp_receive_one_put_flow(tmp_path, monkeypatch):
    payload = b"hello"
    data = (
        b"T0 0 0 0\n"
        b"C0644 5 hello.txt\n"
        + payload
        + b"\x00"
        + b"E\n"
        + b"\n"
    )
    stdout = _set_io(monkeypatch, data)
    monkeypatch.setattr(gateway, "_token", lambda: "tok123")

    created = datetime(2024, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(gateway, "utcnow", lambda: created)

    inserted = []

    def fake_insert_file(**kwargs):
        inserted.append(kwargs)

    monkeypatch.setattr(gateway, "insert_file", fake_insert_file)

    conf = gateway.Config(data_dir=tmp_path, ttl_days=1)
    receipts = gateway.scp_receive_one(conf)

    assert receipts == [
        {
            "token": "tok123",
            "sha512": hashlib.sha512(payload).hexdigest(),
            "expires_at": (created + timedelta(days=1)).isoformat(),
            "original_name": "hello.txt",
            "size_bytes": 5,
            "mode": "0644",
        }
    ]
    assert inserted[0]["stored_path"] == str(tmp_path / "tok123")
    assert (tmp_path / "tok123").read_bytes() == payload
    assert stdout.buffer.getvalue() == gateway.ACK_OK * 5


def test_scp_receive_one_unsupported_record(monkeypatch, tmp_path):
    _set_io(monkeypatch, b"X\n")
    conf = gateway.Config(data_dir=tmp_path, ttl_days=1)

    with pytest.raises(RuntimeError):
        gateway.scp_receive_one(conf)


def test_scp_receive_one_bad_terminator(monkeypatch, tmp_path):
    data = b"C0644 1 a.txt\nx\x01"
    _set_io(monkeypatch, data)
    conf = gateway.Config(data_dir=tmp_path, ttl_days=1)

    with pytest.raises(RuntimeError):
        gateway.scp_receive_one(conf)


def test_scp_receive_one_missing_payload(monkeypatch, tmp_path):
    data = b"C0644 1 a.txt\n"
    _set_io(monkeypatch, data)
    conf = gateway.Config(data_dir=tmp_path, ttl_days=1)

    with pytest.raises(EOFError):
        gateway.scp_receive_one(conf)


def test_parse_c_record_invalid():
    with pytest.raises(RuntimeError):
        gateway._parse_c_record(b"C0644\n")


def test_scp_flags_parse_error():
    flags = gateway._scp_flags('"unterminated')
    assert flags == set()


def test_scp_flags_skips_lone_dash():
    flags = gateway._scp_flags("scp - -t /")
    assert "t" in flags


def test_expect_client_ok_error(monkeypatch):
    _set_io(monkeypatch, b"\x01")
    with pytest.raises(RuntimeError):
        gateway._expect_client_ok()


def test_read_line_eof(monkeypatch):
    _set_io(monkeypatch, b"")
    with pytest.raises(EOFError):
        gateway._read_line()


def test_read_exact_eof(monkeypatch):
    _set_io(monkeypatch, b"")
    with pytest.raises(EOFError):
        gateway._read_exact(1)


def test_scp_send_one_success(tmp_path, monkeypatch):
    path = tmp_path / "file.bin"
    payload = b"data"
    path.write_bytes(payload)

    created = datetime(2024, 1, 1, tzinfo=timezone.utc)
    expires = created + timedelta(days=1)
    row = ("tok", "sha", "orig.txt", len(payload), str(path), created, expires)

    monkeypatch.setattr(gateway, "get_file_by_token", lambda _token: row)
    monkeypatch.setattr(gateway, "utcnow", lambda: created)

    stdout = _set_io(monkeypatch, gateway.ACK_OK * 3)
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)

    gateway.scp_send_one(gateway.Config(data_dir=tmp_path, ttl_days=1), "tok")

    out = stdout.buffer.getvalue()
    assert out.startswith(b"C0644 4 tok\n")
    assert out.endswith(gateway.ACK_OK)
    assert payload in out
    assert "Filename: orig.txt" in stderr.getvalue()


def test_scp_send_one_token_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr(gateway, "get_file_by_token", lambda _token: None)
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)

    with pytest.raises(SystemExit) as exc:
        gateway.scp_send_one(gateway.Config(data_dir=tmp_path, ttl_days=1), "missing")

    assert exc.value.code == 2
    assert "token not found" in stderr.getvalue()


def test_scp_send_one_expired(monkeypatch, tmp_path):
    now = datetime(2024, 1, 2, tzinfo=timezone.utc)
    expired = now - timedelta(seconds=1)
    row = ("tok", "sha", "orig.txt", 1, str(tmp_path / "x"), now, expired)

    monkeypatch.setattr(gateway, "get_file_by_token", lambda _token: row)
    monkeypatch.setattr(gateway, "utcnow", lambda: now)
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)

    with pytest.raises(SystemExit) as exc:
        gateway.scp_send_one(gateway.Config(data_dir=tmp_path, ttl_days=1), "tok")

    assert exc.value.code == 2
    assert "token expired" in stderr.getvalue()


def test_scp_send_one_missing_file(monkeypatch, tmp_path):
    now = datetime(2024, 1, 2, tzinfo=timezone.utc)
    expires = now + timedelta(days=1)
    row = ("tok", "sha", "orig.txt", 1, str(tmp_path / "missing"), now, expires)

    monkeypatch.setattr(gateway, "get_file_by_token", lambda _token: row)
    monkeypatch.setattr(gateway, "utcnow", lambda: now)
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)

    with pytest.raises(SystemExit) as exc:
        gateway.scp_send_one(gateway.Config(data_dir=tmp_path, ttl_days=1), "tok")

    assert exc.value.code == 2
    assert "file missing" in stderr.getvalue()


def test_scp_send_one_bad_ack(monkeypatch, tmp_path):
    path = tmp_path / "file.bin"
    path.write_bytes(b"x")
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    expires = now + timedelta(days=1)
    row = ("tok", "sha", "orig.txt", 1, str(path), now, expires)

    monkeypatch.setattr(gateway, "get_file_by_token", lambda _token: row)
    monkeypatch.setattr(gateway, "utcnow", lambda: now)
    _set_io(monkeypatch, b"\x01")
    monkeypatch.setattr(sys, "stderr", io.StringIO())

    with pytest.raises(RuntimeError):
        gateway.scp_send_one(gateway.Config(data_dir=tmp_path, ttl_days=1), "tok")


def test_main_invalid_usage(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["gateway.py"])
    monkeypatch.setattr(sys, "stderr", io.StringIO())

    with pytest.raises(SystemExit) as exc:
        gateway.main()

    assert exc.value.code == 2


def test_main_put_missing_flag(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["gateway.py", "put"])
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(gateway, "_parse_original_command", lambda: "scp -v /")

    with pytest.raises(SystemExit) as exc:
        gateway.main()

    assert exc.value.code == 2


def test_main_put_success(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["gateway.py", "put"])
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(gateway, "_parse_original_command", lambda: "scp -t /")
    monkeypatch.setattr(
        gateway,
        "scp_receive_one",
        lambda _conf: [
            {"token": "tok", "expires_at": "2024-01-02T00:00:00+00:00"}
        ],
    )

    with pytest.raises(SystemExit) as exc:
        gateway.main()

    assert exc.value.code == 0
    assert "RECEIPT" in stderr.getvalue()


def test_main_put_error(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["gateway.py", "put"])
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(gateway, "_parse_original_command", lambda: "scp -t /")

    def boom(_conf):
        raise RuntimeError("nope")

    monkeypatch.setattr(gateway, "scp_receive_one", boom)

    with pytest.raises(SystemExit) as exc:
        gateway.main()

    assert exc.value.code == 1


def test_main_get_missing_flag(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["gateway.py", "get"])
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(gateway, "_parse_original_command", lambda: "scp -t token")

    with pytest.raises(SystemExit) as exc:
        gateway.main()

    assert exc.value.code == 2


def test_main_get_missing_token(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["gateway.py", "get"])
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(gateway, "_parse_original_command", lambda: "scp -f")

    with pytest.raises(SystemExit) as exc:
        gateway.main()

    assert exc.value.code == 2


def test_main_get_success(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["gateway.py", "get"])
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(gateway, "_parse_original_command", lambda: "scp -f token")

    called = {"count": 0}

    def fake_send(_conf, _token):
        called["count"] += 1

    monkeypatch.setattr(gateway, "scp_send_one", fake_send)

    with pytest.raises(SystemExit) as exc:
        gateway.main()

    assert exc.value.code == 0
    assert called["count"] == 1


def test_main_get_error(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["gateway.py", "get"])
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(gateway, "_parse_original_command", lambda: "scp -f token")

    def boom(_conf, _token):
        raise RuntimeError("nope")

    monkeypatch.setattr(gateway, "scp_send_one", boom)

    with pytest.raises(SystemExit) as exc:
        gateway.main()

    assert exc.value.code == 1


def test_parse_original_command(monkeypatch):
    monkeypatch.setenv("SSH_ORIGINAL_COMMAND", "scp -t /")
    assert gateway._parse_original_command() == "scp -t /"


def test_gateway_entrypoint_runs_main(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["gateway.py"])
    monkeypatch.setattr(sys, "stderr", io.StringIO())

    sys.modules.pop("app.gateway", None)
    with pytest.raises(SystemExit) as exc:
        __import__("runpy").run_module("app.gateway", run_name="__main__")

    assert exc.value.code == 2
