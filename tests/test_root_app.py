"""Tests proving the original root application (app/) still works."""

from fastapi.testclient import TestClient

from app import main as root_main


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


def test_root_info_endpoint():
    """GET / still returns the original info message."""
    with TestClient(root_main.app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "mensaje": "API de ReservasPyS funcionando correctamente"
    }


def test_root_health_ok(monkeypatch):
    """GET /health succeeds when the database answers (faked, no network)."""
    monkeypatch.setattr(root_main, "obtener_conexion", lambda: FakeConnection())
    with TestClient(root_main.app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"api": "ok", "base_de_datos": "conectada"}


def test_root_health_503_when_database_fails(monkeypatch):
    """GET /health returns 503 when the database is unreachable."""

    def _raise():
        raise OSError("connection refused (simulated)")

    monkeypatch.setattr(root_main, "obtener_conexion", _raise)
    with TestClient(root_main.app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["detail"] == "No se pudo conectar con la base de datos"
