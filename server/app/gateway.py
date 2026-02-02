#!/usr/bin/env python3
import os
import re
import shlex
import sys
import traceback
import secrets
import hashlib
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from app.db import insert_file, get_file_by_token, utcnow
from app import logutil

ACK_OK = b"\x00"


@dataclass
class Config:
    data_dir: Path
    ttl_days: int


def cfg() -> Config:
    data_dir = Path(os.environ.get("DATA_DIR", "/data")).resolve()
    ttl_days = int(os.environ.get("TTL_DAYS", "7"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return Config(data_dir=data_dir, ttl_days=ttl_days)


def _stderr(msg: str) -> None:
    sys.stderr.write(msg)
    sys.stderr.flush()


def _read_exact(n: int) -> bytes:
    buf = b""
    r = sys.stdin.buffer
    while len(buf) < n:
        chunk = r.read(n - len(buf))
        if not chunk:
            raise EOFError("unexpected EOF")
        buf += chunk
    return buf


def _read_line() -> bytes:
    line = sys.stdin.buffer.readline()
    if not line:
        raise EOFError("unexpected EOF")
    return line


def _send_ok() -> None:
    sys.stdout.buffer.write(ACK_OK)
    sys.stdout.buffer.flush()


def _expect_client_ok() -> None:
    b = _read_exact(1)
    # scp uses \0 for ok; others for errors; treat non-ok as failure
    if b != ACK_OK:
        raise RuntimeError(f"client did not ACK OK: {b!r}")


def _token() -> str:
    # URL-safe token, high entropy
    return secrets.token_urlsafe(32)


def _parse_original_command() -> str:
    return os.environ.get("SSH_ORIGINAL_COMMAND", "").strip()


def _scp_flags(cmd: str) -> set[str]:
    """
    Extract short option flags from an scp command string.
    Handles combined flags like -vt and separate -v -t.
    """
    flags: set[str] = set()
    try:
        parts = shlex.split(cmd)
    except ValueError:
        logutil.warning(f"failed to parse SSH_ORIGINAL_COMMAND: {cmd!r}")
        return flags
    for p in parts:
        if p.startswith("-") and not p.startswith("--") and len(p) > 1:
            # Skip a lone "-" (shouldn't happen).
            if p == "-":
                continue
            for ch in p[1:]:
                flags.add(ch)
    return flags


def scp_receive_one(conf: Config) -> list[dict]:
    """
    Minimal scp -t receiver.
    Supports multiple files (C records) in one session.
    Returns receipts for each received file.
    """
    receipts: list[dict] = []
    logutil.debug("scp_receive_one: sending initial ACK")
    _send_ok()  # initial ack

    while True:
        try:
            line = _read_line()
        except EOFError:
            break

        if line.startswith(b"T"):
            # timestamps line: accept, ignore
            logutil.verbose("scp_receive_one: received T record")
            _send_ok()
            continue

        if line.startswith(b"C"):
            # C<mode> <size> <filename>\n
            try:
                parts = line.decode("utf-8", errors="replace").strip().split(" ", 2)
                mode = parts[0][1:]
                size = int(parts[1])
                filename = parts[2]
            except Exception as e:
                raise RuntimeError(f"bad C record: {line!r} ({e})")

            logutil.debug(
                f"scp_receive_one: C record mode={mode} size={size} filename={filename!r}"
            )
            _send_ok()  # ack header

            token = _token()
            tmp_path = conf.data_dir / f".{token}.tmp"
            final_path = conf.data_dir / token

            h = hashlib.sha512()
            remaining = size
            with open(tmp_path, "wb") as f:
                while remaining > 0:
                    chunk = sys.stdin.buffer.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise EOFError("unexpected EOF while reading file data")
                    f.write(chunk)
                    h.update(chunk)
                    remaining -= len(chunk)
                    logutil.verbose(f"scp_receive_one: remaining={remaining}")

            # file terminator
            term = _read_exact(1)
            if term != ACK_OK:
                raise RuntimeError(f"missing file terminator, got {term!r}")

            os.replace(tmp_path, final_path)
            _send_ok()  # ack file received

            created = utcnow()
            expires = created + timedelta(days=conf.ttl_days)
            digest = h.hexdigest()

            logutil.info(
                f"scp_receive_one: insert_file token={token} size={size} sha512={digest[:16]}..."
            )
            insert_file(
                token=token,
                sha512=digest,
                original_name=filename,
                size_bytes=size,
                stored_path=str(final_path),
                created_at=created,
                expires_at=expires,
            )

            receipts.append(
                {
                    "token": token,
                    "sha512": digest,
                    "expires_at": expires.isoformat(),
                    "original_name": filename,
                    "size_bytes": size,
                    "mode": mode,
                }
            )
            continue

        if line.startswith(b"E"):
            _send_ok()
            continue

        # Some clients may send blank; stop on EOF only
        if line.strip() == b"":
            continue

        raise RuntimeError(f"unsupported scp record: {line!r}")

    return receipts


def scp_send_one(conf: Config, token: str) -> None:
    """
    Minimal scp -f sender for a single token.
    """
    logutil.debug(f"scp_send_one: lookup token={token!r}")
    row = get_file_by_token(token)
    if not row:
        _stderr("ERROR: token not found\n")
        logutil.warning(f"scp_send_one: token not found token={token!r}")
        sys.exit(2)

    _, _, _, size_bytes, stored_path, _, expires_at = row
    now = utcnow()
    if now >= expires_at:
        _stderr("ERROR: token expired\n")
        logutil.info(f"scp_send_one: token expired token={token!r}")
        sys.exit(2)

    path = Path(stored_path)
    if not path.exists():
        _stderr("ERROR: file missing on disk\n")
        logutil.error(f"scp_send_one: file missing token={token!r} path={stored_path}")
        sys.exit(2)

    logutil.debug("scp_send_one: waiting for initial client ACK")
    _expect_client_ok()

    header = f"C0644 {size_bytes} {token}\n".encode("utf-8")
    sys.stdout.buffer.write(header)
    sys.stdout.buffer.flush()

    logutil.debug("scp_send_one: waiting for client ACK after header")
    _expect_client_ok()

    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            sys.stdout.buffer.write(chunk)
    sys.stdout.buffer.write(ACK_OK)
    sys.stdout.buffer.flush()

    logutil.debug("scp_send_one: waiting for final client ACK")
    _expect_client_ok()


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("put", "get"):
        _stderr("FATAL: usage: gateway.py [put|get]\n")
        sys.exit(2)

    mode = sys.argv[1]
    conf = cfg()
    cmd = _parse_original_command()
    flags = _scp_flags(cmd)
    logutil.info(
        f"mode={mode} cmd={cmd!r} flags={''.join(sorted(flags)) or '-'} data_dir={conf.data_dir}"
    )

    if mode == "put":
        if "t" not in flags:
            _stderr("ERROR: only scp upload is allowed (scp -t)\n")
            sys.exit(2)
        try:
            receipts = scp_receive_one(conf)
        except Exception as e:
            logutil.error(f"upload failed: {e!r}")
            logutil.debug(traceback.format_exc())
            _stderr(f"ERROR: upload failed: {e}\n")
            sys.exit(1)

        # Receipt on stderr to avoid corrupting scp stdout protocol
        for r in receipts:
            _stderr(
                "RECEIPT\n"
                f"token={r['token']}\n"
                f"expires_at={r['expires_at']}\n"
            )
        sys.exit(0)

    if mode == "get":
        if "f" not in flags:
            _stderr("ERROR: only scp download is allowed (scp -f <token>)\n")
            sys.exit(2)

        # SSH_ORIGINAL_COMMAND from scp looks like: scp -f <path>
        parts = cmd.split()
        if len(parts) < 3:
            _stderr("ERROR: missing token\n")
            logutil.warning(f"download failed: missing token cmd={cmd!r}")
            sys.exit(2)
        token = parts[-1].strip()

        try:
            scp_send_one(conf, token)
        except Exception as e:
            logutil.error(f"download failed: {e!r}")
            logutil.debug(traceback.format_exc())
            _stderr(f"ERROR: download failed: {e}\n")
            sys.exit(1)

        sys.exit(0)


if __name__ == "__main__":
    main()
