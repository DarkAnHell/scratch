import os
import re
import subprocess
import hashlib
from datetime import datetime, timezone

SSH_HOST = os.environ.get("SSH_HOST", "sshpoc")
SSH_PORT = os.environ.get("SSH_PORT", "22")
KEYS_DIR = os.environ.get("KEYS_DIR", "/keys")

COMMON_OPTS = [
    "-o", "StrictHostKeyChecking=no",
    "-o", "UserKnownHostsFile=/dev/null",
    "-o", "LogLevel=ERROR",
    "-P", str(SSH_PORT),
]

RE_TOKEN = re.compile(r"^token=(.+)$", re.M)
RE_SHA = re.compile(r"^sha512=([0-9a-f]{128})$", re.M)
RE_EXPIRES = re.compile(r"^expires_at=(.+)$", re.M)

def run(cmd, *, check=True, capture=True):
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )

def sha512_file(path: str) -> str:
    h = hashlib.sha512()
    with open(path, "rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def test_put_then_get_roundtrip(tmp_path):
    src = tmp_path / "hello.txt"
    src.write_text("hello poc\n", encoding="utf-8")
    expected_sha = sha512_file(str(src))

    put_key = os.path.join(KEYS_DIR, "put")
    get_key = os.path.join(KEYS_DIR, "get")

    # Upload
    p = run([
        "scp", *COMMON_OPTS,
        "-i", put_key,
        str(src),
        f"put@{SSH_HOST}:/",
    ])

    # Receipt is on stderr
    m_tok = RE_TOKEN.search(p.stderr or "")
    m_sha = RE_SHA.search(p.stderr or "")
    m_exp = RE_EXPIRES.search(p.stderr or "")
    assert m_tok, f"missing token in receipt stderr:\n{p.stderr}"
    assert m_sha, f"missing sha512 in receipt stderr:\n{p.stderr}"
    assert m_exp, f"missing expires_at in receipt stderr:\n{p.stderr}"

    token = m_tok.group(1).strip()
    got_sha = m_sha.group(1).strip()
    expires_at = m_exp.group(1).strip()

    assert got_sha == expected_sha

    # Expires ~7 days from now (allow a few minutes skew)
    exp_dt = datetime.fromisoformat(expires_at)
    now = datetime.now(timezone.utc)
    delta = exp_dt - now
    assert 6.9 * 24 * 3600 <= delta.total_seconds() <= 7.1 * 24 * 3600

    # Download
    dst = tmp_path / "out.txt"
    run([
        "scp", *COMMON_OPTS,
        "-i", get_key,
        f"get@{SSH_HOST}:{token}",
        str(dst),
    ])

    assert dst.read_bytes() == src.read_bytes()

def test_invalid_token_fails(tmp_path):
    get_key = os.path.join(KEYS_DIR, "get")
    dst = tmp_path / "nope.bin"
    r = subprocess.run(
        [
            "scp", *COMMON_OPTS,
            "-i", get_key,
            f"get@{SSH_HOST}:does-not-exist",
            str(dst),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert r.returncode != 0