from __future__ import annotations

from datetime import datetime, timezone

from app import db


class DummyConn:
    def __init__(self, fetchone_result=None, fetchall_result=None):
        self.fetchone_result = fetchone_result
        self.fetchall_result = fetchall_result
        self.queries: list[tuple[str, tuple | None]] = []

    def execute(self, query: str, params: tuple | None = None):
        self.queries.append((query, params))
        return self

    def fetchone(self):
        return self.fetchone_result

    def fetchall(self):
        return self.fetchall_result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_dsn_from_env(monkeypatch):
    monkeypatch.setenv("DB_HOST", "db")
    monkeypatch.setenv("DB_PORT", "5439")
    monkeypatch.setenv("DB_NAME", "app")
    monkeypatch.setenv("DB_USER", "user")
    monkeypatch.setenv("DB_PASSWORD", "pw")

    dsn = db._dsn()

    assert "host=db" in dsn
    assert "port=5439" in dsn
    assert "dbname=app" in dsn
    assert "user=user" in dsn
    assert "password=pw" in dsn


def test_init_db_executes_schema(monkeypatch):
    dummy = DummyConn()
    monkeypatch.setattr(db.psycopg, "connect", lambda _dsn: dummy)
    monkeypatch.setenv("DB_HOST", "db")
    monkeypatch.setenv("DB_NAME", "app")
    monkeypatch.setenv("DB_USER", "user")
    monkeypatch.setenv("DB_PASSWORD", "pw")

    db.init_db()

    assert len(dummy.queries) == 2
    assert "CREATE TABLE" in dummy.queries[0][0]
    assert "CREATE INDEX" in dummy.queries[1][0]


def test_insert_file_executes(monkeypatch):
    dummy = DummyConn()
    monkeypatch.setattr(db.psycopg, "connect", lambda _dsn: dummy)
    monkeypatch.setenv("DB_HOST", "db")
    monkeypatch.setenv("DB_NAME", "app")
    monkeypatch.setenv("DB_USER", "user")
    monkeypatch.setenv("DB_PASSWORD", "pw")

    now = datetime.now(timezone.utc)
    db.insert_file(
        token="tok",
        sha512="sha",
        original_name="file.txt",
        size_bytes=1,
        stored_path="/tmp/file",
        created_at=now,
        expires_at=now,
    )

    assert len(dummy.queries) == 1
    assert "INSERT INTO files" in dummy.queries[0][0]


def test_get_file_by_token(monkeypatch):
    row = ("tok", "sha", "name", 1, "/tmp/file", datetime.now(timezone.utc), datetime.now(timezone.utc))
    dummy = DummyConn(fetchone_result=row)
    monkeypatch.setattr(db.psycopg, "connect", lambda _dsn: dummy)
    monkeypatch.setenv("DB_HOST", "db")
    monkeypatch.setenv("DB_NAME", "app")
    monkeypatch.setenv("DB_USER", "user")
    monkeypatch.setenv("DB_PASSWORD", "pw")

    result = db.get_file_by_token("tok")

    assert result == row
    assert len(dummy.queries) == 1
    assert "SELECT token" in dummy.queries[0][0]


def test_delete_expired(monkeypatch):
    rows = [("tok1", "/tmp/1"), ("tok2", "/tmp/2")]
    dummy = DummyConn(fetchall_result=rows)
    monkeypatch.setattr(db.psycopg, "connect", lambda _dsn: dummy)
    monkeypatch.setenv("DB_HOST", "db")
    monkeypatch.setenv("DB_NAME", "app")
    monkeypatch.setenv("DB_USER", "user")
    monkeypatch.setenv("DB_PASSWORD", "pw")

    now = datetime.now(timezone.utc)
    result = db.delete_expired(now)

    assert result == rows
    assert len(dummy.queries) == 2
    assert "SELECT token" in dummy.queries[0][0]
    assert "DELETE FROM files" in dummy.queries[1][0]


def test_utcnow_timezone():
    now = db.utcnow()
    assert now.tzinfo is timezone.utc
