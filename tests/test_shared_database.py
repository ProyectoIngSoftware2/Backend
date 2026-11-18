"""Tests for the shared database helpers (no real connection opened)."""

import psycopg

from shared import database


class FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, query, params=None):  # noqa: ARG002
        return None

    def fetchone(self):
        return (1,)


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def cursor(self):
        return FakeCursor()


def test_check_connection_true_when_database_answers(monkeypatch):
    monkeypatch.setattr(database, "get_connection", lambda row_factory=None: FakeConnection())
    assert database.check_connection() is True


def test_check_connection_false_on_failure(monkeypatch):
    def _raise(row_factory=None):
        raise OSError("connection refused (simulated)")

    monkeypatch.setattr(database, "get_connection", _raise)
    assert database.check_connection() is False


def test_check_connection_false_on_psycopg_error(monkeypatch):
    """psycopg connection failures are contained and reported as False."""
    def _raise(row_factory=None):
        raise psycopg.OperationalError("connection refused (simulated)")

    monkeypatch.setattr(database, "get_connection", _raise)
    assert database.check_connection() is False
