from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

import psycopg

from app import logutil

ExpiredRow = tuple[str, str]


def _dsn() -> str:
    # Read DB connection info from environment for container flexibility.
    host = os.environ["DB_HOST"]
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ["DB_NAME"]
    user = os.environ["DB_USER"]
    pw = os.environ["DB_PASSWORD"]
    logutil.debug(f"db dsn host={host} port={port} dbname={name} user={user}")
    return f"host={host} port={port} dbname={name} user={user} password={pw}"


@contextmanager
def conn() -> Iterator[psycopg.Connection]:
    logutil.verbose("db connecting")
    with psycopg.connect(_dsn()) as c:
        yield c
    logutil.verbose("db connection closed")


def init_db() -> None:
    # Idempotent schema initialization.
    logutil.info("db init schema")
    with conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
              token TEXT PRIMARY KEY,
              sha512 TEXT NOT NULL,
              original_name TEXT NOT NULL,
              size_bytes BIGINT NOT NULL,
              stored_path TEXT NOT NULL,
              created_at TIMESTAMPTZ NOT NULL,
              expires_at TIMESTAMPTZ NOT NULL
            );
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_expires_at ON files(expires_at);"
        )
    logutil.debug("db init complete")


def insert_file(
    *,
    token: str,
    sha512: str,
    original_name: str,
    size_bytes: int,
    stored_path: str,
    created_at: datetime,
    expires_at: datetime,
) -> None:
    logutil.debug(
        f"db insert token={token} size_bytes={size_bytes} name={original_name!r}"
    )
    with conn() as c:
        c.execute(
            """
            INSERT INTO files(token, sha512, original_name, size_bytes, stored_path, created_at, expires_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                token,
                sha512,
                original_name,
                size_bytes,
                stored_path,
                created_at,
                expires_at,
            ),
        )
    logutil.verbose("db insert complete")


def get_file_by_token(
    token: str,
) -> tuple[str, str, str, int, str, datetime, datetime] | None:
    logutil.debug(f"db lookup token={token}")
    with conn() as c:
        row = c.execute(
            "SELECT token, sha512, original_name, size_bytes, stored_path, created_at, expires_at FROM files WHERE token=%s",
            (token,),
        ).fetchone()
        logutil.verbose(f"db lookup token={token} found={row is not None}")
        return row


def delete_expired(now: datetime) -> list[ExpiredRow]:
    """
    Returns list of (token, stored_path) deleted from DB.
    """
    logutil.debug(f"db delete_expired now={now.isoformat()}")
    with conn() as c:
        rows = c.execute(
            "SELECT token, stored_path FROM files WHERE expires_at <= %s",
            (now,),
        ).fetchall()
        c.execute("DELETE FROM files WHERE expires_at <= %s", (now,))
        logutil.info(f"db delete_expired deleted={len(rows)}")
        return [(r[0], r[1]) for r in rows]


def utcnow() -> datetime:
    # Centralized time source for easier testing/mocking.
    return datetime.now(timezone.utc)
