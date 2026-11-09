"""Shared pytest configuration and fakes for the Punto y Sal backend.

The unit tests never touch the network or the database: database access
is replaced with small fake objects so the suite is deterministic and
never performs writes.

Authentication: the suite runs with a test-only JWT secret injected via
the environment (never committed, never the production value). It is set
with ``setdefault`` so an explicitly provided ``JWT_SECRET`` (e.g. a
developer's local .env value exported in the shell) always wins.
"""

import os
import sys
from pathlib import Path

# Make the repository root importable (shared/, services/, gateway/, app/).
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Test-only JWT signing secret (>= 64 characters: enough for HS512 too,
# required minimum by shared.auth is 32). Lives only in this process's
# environment: it is not a real credential and is never written to any
# file.
os.environ.setdefault(
    "JWT_SECRET",
    "pys-unit-tests-only-secret-do-not-use-in-production-0123456789abcdef",
)

import psycopg
import pytest
from fastapi.testclient import TestClient

from shared.auth import ROLE_ADMIN, ROLE_CLIENT, create_access_token


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


class ScriptedCursor(FakeCursor):
    """FakeCursor whose execute() can raise scripted database errors.

    ``effects`` holds one entry per execute() call, consumed in order:
    an exception instance (or exception class) is raised, ``None`` (or
    anything else) lets the call succeed. fetchone()/fetchall() keep the
    canned behaviour of FakeCursor.
    """

    def __init__(self, one_results=(), all_results=(), executed=None, effects=None):
        super().__init__(one_results, all_results, executed)
        self._effects = list(effects) if effects else []

    def execute(self, query, params=None):
        self._executed.append((query, params))
        if self._effects:
            effect = self._effects.pop(0)
            if isinstance(effect, type) and issubclass(effect, Exception):
                raise effect()
            if isinstance(effect, BaseException):
                raise effect
        return None


class ScriptedConnection(FakeConnection):
    """FakeConnection whose cursors raise the scripted effects."""

    def __init__(self, one_results=(), all_results=(), effects=()):
        super().__init__(one_results, all_results)
        self._effects = list(effects) if effects else []

    def cursor(self):
        return ScriptedCursor(
            self._one_results, self._all_results, self.executed, self._effects
        )


def trigger_error(message: str) -> Exception:
    """Build a psycopg P0001 (RaiseException) carrying ``message``.

    Mirrors what an approved business-rule trigger raises
    (RAISE EXCEPTION '...'), including diag.message_primary, so the
    services' 400 mapping can be asserted with the real message.
    ``psycopg.Error.diag`` is a read-only property, so a subclass with
    its own ``diag`` property provides the value.
    """

    class _TriggerError(psycopg.errors.RaiseException):
        @property
        def diag(self):
            class _Diag:
                pass

            diag = _Diag()
            diag.message_primary = message
            return diag

    return _TriggerError(message)


@pytest.fixture
def scripted_service_db(monkeypatch):
    """Like patch_service_db, but execute() can raise scripted errors.

    Usage:
        scripted_service_db(module, one_results=[row], effects=[None,
                            trigger_error("bad transition")])
    The connection is exposed as ``scripted_service_db.last_connection``.
    """

    def _patch(module, one_results=(), all_results=(), effects=(), healthy=True):
        monkeypatch.setattr(module, "check_connection", lambda: healthy)
        connection = ScriptedConnection(one_results, all_results, effects)
        monkeypatch.setattr(
            module,
            "get_connection",
            lambda row_factory=None: connection,
        )
        _patch.last_connection = connection

    _patch.last_connection = None
    return _patch


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


# ---------------------------------------------------------------------------
# Authentication fixtures (Sprint 2)
# ---------------------------------------------------------------------------


@pytest.fixture
def token_for():
    """Factory: ``token_for(id_usuario, rol, **claims)`` -> signed JWT.

    Produces genuinely signed tokens with the test-only secret, so the
    endpoints exercise their real validation path (signature,
    expiration, role). ``iat``/``exp`` are always added by
    ``create_access_token``; extra profile claims (``id_cliente``,
    ``id_administrador``) can be passed explicitly.
    """

    def _make(id_usuario: int, rol: str, **claims) -> str:
        # No profile claims are added implicitly: tests that need an
        # ownership profile must pass id_cliente / id_administrador
        # explicitly (this also lets them build profile-less tokens).
        return create_access_token(
            id_usuario=id_usuario,
            rol=rol,
            correo=claims.pop("correo", "prueba@puntoysal.test"),
            **claims,
        )

    return _make


@pytest.fixture
def admin_headers(token_for):
    """Authorization headers of a valid administrator token."""
    token = token_for(1, ROLE_ADMIN, id_administrador=1)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client_headers(token_for):
    """Authorization headers of a valid client token (id_cliente=1)."""
    token = token_for(2, ROLE_CLIENT, id_cliente=1)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Live (integration) authentication helpers
# ---------------------------------------------------------------------------
# The credentials of the local/integration test accounts are read from
# the environment ONLY: they are never written to this file or any other
# file tracked by Git. Run the live suite with, for example:
#
#   TEST_ADMIN_CORREO=... TEST_ADMIN_PASSWORD=... \
#   TEST_CLIENT_CORREO=... TEST_CLIENT_PASSWORD=... \
#   RUN_DB_TESTS=1 pytest -m integration

_LIVE_ACCOUNT_ENV = {
    "admin": ("TEST_ADMIN_CORREO", "TEST_ADMIN_PASSWORD", ROLE_ADMIN),
    "cliente": ("TEST_CLIENT_CORREO", "TEST_CLIENT_PASSWORD", ROLE_CLIENT),
}


@pytest.fixture
def live_credentials():
    """Return ``_get(kind)`` -> (correo, password) from the environment.

    ``kind`` is ``"admin"`` or ``"cliente"``. Skips the test when the
    variables are not exported (credentials never live in Git).
    """

    def _get(kind: str):
        correo_var, password_var, _rol = _LIVE_ACCOUNT_ENV[kind]
        correo = os.getenv(correo_var)
        password = os.getenv(password_var)
        if not correo or not password:
            pytest.skip(
                f"set {correo_var} and {password_var} to run live auth tests"
            )
        return correo, password

    return _get


@pytest.fixture
def live_login(live_credentials):
    """Return ``_login(kind)`` -> login JSON body of a test account.

    Performs a real ``POST /api/v1/auth/login`` against the clientes
    microservice (the owner of the ``usuarios`` table and the only
    service that exposes the login route) and asserts the account
    authenticates with the expected role. The returned access_token can
    then be used on any service.
    """

    def _login(kind: str) -> dict:
        from services.clientes.app import main as clientes_main

        correo, password = live_credentials(kind)
        expected_rol = _LIVE_ACCOUNT_ENV[kind][2]
        with TestClient(clientes_main.app) as login_client:
            response = login_client.post(
                "/api/v1/auth/login",
                json={"correo": correo, "password": password},
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["rol"] == expected_rol
        assert body["access_token"]
        return body

    return _login
