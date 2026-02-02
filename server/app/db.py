import os
from contextlib import contextmanager
from datetime import datetime, timezone
import psycopg

def _dsn() -> str:
    host = os.environ["DB_HOST"]
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ["DB_NAME"]
    user = os.environ["DB_USER"]
    pw = os.environ["DB_PASSWORD"]
    return f"host={host} port={port} dbname={name} user={user} password={pw}"

@contextmanager
def conn():
    with psycopg.connect(_dsn()) as c:
        yield c

def init_db() -> None:
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
        c.execute("CREATE INDEX IF NOT EXISTS idx_files_expires_at ON files(expires_at);")

def insert_file(*, token: str, sha512: str, original_name: str, size_bytes: int, stored_path: str,
                created_at: datetime, expires_at: datetime) -> None:
    with conn() as c:
        c.execute(
            """
            INSERT INTO files(token, sha512, original_name, size_bytes, stored_path, created_at, expires_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,
            (token, sha512, original_name, size_bytes, stored_path, created_at, expires_at),
        )

def get_file_by_token(token: str):
    with conn() as c:
        row = c.execute(
            "SELECT token, sha512, original_name, size_bytes, stored_path, created_at, expires_at FROM files WHERE token=%s",
            (token,),
        ).fetchone()
        return row

def delete_expired(now: datetime) -> list[tuple[str, str]]:
    """
    Returns list of (token, stored_path) deleted from DB.
    """
    with conn() as c:
        rows = c.execute(
            "SELECT token, stored_path FROM files WHERE expires_at <= %s",
            (now,),
        ).fetchall()
        c.execute("DELETE FROM files WHERE expires_at <= %s", (now,))
        return [(r[0], r[1]) for r in rows]

def utcnow() -> datetime:
    return datetime.now(timezone.utc)