"""Shared pytest configuration and fakes for the Punto y Sal backend.

The unit tests never touch the network or the database: database access
is replaced with small fake objects so the suite is deterministic and
never performs writes.
"""

import sys
from pathlib import Path

# Make the repository root importable (shared/, services/, gateway/, app/).
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import psycopg
import pytest


class FakeCursor:
    """Minimal cursor stand-in returning canned results per call.

    Every (query, params) pair passed to execute() is recorded on the
    connection's ``executed`` list so tests can assert that SQL and
    parameters are kept separate.
    """

    def __init__(self, one_results=(), all_results=(), executed=None):
        self._one_results = list(one_results)
        self._all_results = list(all_results)
        self._one_index = 0
        self._all_index = 0
        self._executed = executed if executed is not None else []

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, query, params=None):
        self._executed.append((query, params))
        return None

    def fetchone(self):
        if self._one_index >= len(self._one_results):
            return None
        result = self._one_results[self._one_index]
        self._one_index += 1
        return result

    def fetchall(self):
        if self._all_index >= len(self._all_results):
            return []
        result = self._all_results[self._all_index]
        self._all_index += 1
        return result


class FakeConnection:
    """Minimal connection stand-in usable as a context manager."""

    def __init__(self, one_results=(), all_results=()):
        self._one_results = one_results
        self._all_results = all_results
        # (query, params) pairs executed through any cursor of this
        # connection, for parameterization assertions.
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def cursor(self):
        return FakeCursor(self._one_results, self._all_results, self.executed)


@pytest.fixture
def patch_service_db(monkeypatch):
    """Patch a service module's database functions with deterministic fakes.

    Usage:
        patch_service_db(services.clientes.app.main,
                         all_results=[[]])          # empty list endpoints
        patch_service_db(module, one_results=[None]) # not-found detail

    The FakeConnection that was installed is exposed afterwards as
    ``patch_service_db.last_connection`` (with its ``executed`` log).
    """

    def _patch(module, one_results=(), all_results=(), healthy=True):
        monkeypatch.setattr(module, "check_connection", lambda: healthy)
        connection = FakeConnection(one_results, all_results)
        monkeypatch.setattr(
            module,
            "get_connection",
            lambda row_factory=None: connection,
        )
        _patch.last_connection = connection

    _patch.last_connection = None
    return _patch


@pytest.fixture
def failing_connection(monkeypatch):
    """Make a module's get_connection raise a psycopg connection error.

    This is the exception psycopg raises when the database is
    unreachable, so the services must map it to HTTP 503.
    """

    def _fail(module):
        def _raise(row_factory=None):
            raise psycopg.OperationalError("connection refused (simulated)")

        monkeypatch.setattr(module, "get_connection", _raise)
        monkeypatch.setattr(module, "check_connection", lambda: False)

    return _fail


@pytest.fixture
def unexpected_failure(monkeypatch):
    """Make a module's get_connection raise a non-database bug.

    Per the post-audit error handling, this must NOT become a 503: it is
    an unexpected internal error and must surface as a generic 500.
    """

    def _fail(module):
        def _raise(row_factory=None):
            raise RuntimeError("unexpected internal bug (simulated)")

        monkeypatch.setattr(module, "get_connection", _raise)
        monkeypatch.setattr(module, "check_connection", lambda: False)

    return _fail
