"""Unit tests for the API Gateway (in-process HTTP routing, no sockets).

The gateway proxies real HTTP requests; the tests route those requests to
the actual microservice ASGI applications so the full path is exercised
without opening network ports or touching the database.
"""

import httpx
from fastapi.testclient import TestClient

from gateway.app import main as gateway_main
from services.catalogo.app import main as catalogo_main
from services.clientes.app import main as clientes_main
from services.reservas.app import main as reservas_main

SERVICE_APPS = {
    "http://localhost:8001": clientes_main.app,
    "http://localhost:8002": reservas_main.app,
    "http://localhost:8003": catalogo_main.app,
}


class ServiceRouterTransport(httpx.AsyncBaseTransport):
    """Routes requests by origin to in-process ASGI apps (or raises errors)."""

    def __init__(self, apps=None, errors=None):
        self.apps = apps if apps is not None else SERVICE_APPS
        self.errors = errors or {}

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        origin = f"{request.url.scheme}://{request.url.host}:{request.url.port}"
        if origin in self.errors:
            raise self.errors[origin](request=request)
        target = self.apps.get(origin)
        if target is None:
            raise httpx.ConnectError("connection refused", request=request)
        transport = httpx.ASGITransport(app=target)
        return await transport.handle_async_request(request)


def make_client(transport=None):
    """Start the gateway and replace its HTTP client with the test transport.

    Both HTTP clients are closed properly: the real lifespan-created
    client is closed inside the TestClient's own event loop before it is
    replaced, and the replacement client is closed by the lifespan
    shutdown when the client exits.
    """
    client = TestClient(gateway_main.app)
    client.__enter__()  # runs lifespan: creates app.state.client
    if transport is not None:
        original = gateway_main.app.state.client
        gateway_main.app.state.client = httpx.AsyncClient(
            transport=transport, timeout=5.0
        )
        # Close the unused real client inside its original event loop.
        client.portal.call(original.aclose)
    return client


def test_gateway_health():
    """Gateway /health works without contacting any downstream service."""
    client = make_client()
    try:
        response = client.get("/health")
    finally:
        client.__exit__(None, None, None)
    assert response.status_code == 200
    assert response.json() == {"service": "gateway", "status": "ok"}


def test_gateway_services_health_all_ok(patch_service_db):
    """/health/services reports all three microservices as ok."""
    for module in (clientes_main, reservas_main, catalogo_main):
        patch_service_db(module, healthy=True)
    client = make_client(ServiceRouterTransport())
    try:
        response = client.get("/health/services")
    finally:
        client.__exit__(None, None, None)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["downstream"] == {
        "clientes": "ok",
        "reservas": "ok",
        "catalogo": "ok",
    }


def test_gateway_services_health_degraded():
    """/health/services reports degraded when services are unreachable."""
    errors = {
        origin: (lambda request: httpx.ConnectError("refused", request=request))
        for origin in SERVICE_APPS
    }
    client = make_client(ServiceRouterTransport(apps={}, errors=errors))
    try:
        response = client.get("/health/services")
    finally:
        client.__exit__(None, None, None)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["downstream"] == {
        "clientes": "unavailable",
        "reservas": "unavailable",
        "catalogo": "unavailable",
    }


def test_gateway_routes_to_all_three_services(patch_service_db, admin_headers):
    """GET /api/v1/... is proxied to the correct microservice."""
    patch_service_db(clientes_main, all_results=[[]])
    patch_service_db(reservas_main, all_results=[[]])
    patch_service_db(catalogo_main, all_results=[[]])

    client = make_client(ServiceRouterTransport())
    try:
        clientes = client.get("/api/v1/clientes", headers=admin_headers)
        reservas = client.get("/api/v1/reservas", headers=admin_headers)
        mesas = client.get("/api/v1/catalogo/mesas")
        platillos = client.get("/api/v1/catalogo/platillos")
    finally:
        client.__exit__(None, None, None)

    assert clientes.status_code == 200
    assert clientes.json() == {"data": []}
    assert reservas.status_code == 200
    assert reservas.json() == {"data": []}
    assert mesas.status_code == 200
    assert mesas.json() == {"data": []}
    assert platillos.status_code == 200
    assert platillos.json() == {"data": []}


def test_gateway_routes_detail_and_404(patch_service_db, admin_headers):
    """A downstream 404 passes through the gateway untouched."""
    patch_service_db(clientes_main, one_results=[None])
    client = make_client(ServiceRouterTransport())
    try:
        response = client.get("/api/v1/clientes/999999", headers=admin_headers)
    finally:
        client.__exit__(None, None, None)
    assert response.status_code == 404
    assert response.json()["detail"] == "Customer not found"


def test_gateway_returns_503_when_service_unavailable():
    """Unreachable service produces a controlled JSON 503 (no internals)."""
    errors = {
        "http://localhost:8001": (
            lambda request: httpx.ConnectError("refused", request=request)
        )
    }
    client = make_client(ServiceRouterTransport(apps={}, errors=errors))
    try:
        response = client.get("/api/v1/clientes")
    finally:
        client.__exit__(None, None, None)
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Service 'clientes' is unavailable",
        "service": "clientes",
    }
    # No internal URLs or stack traces leak to the caller.
    assert "localhost" not in response.text
    assert "Traceback" not in response.text


def test_gateway_returns_504_on_timeout():
    """A slow service produces a controlled JSON 504."""
    errors = {
        "http://localhost:8002": (
            lambda request: httpx.ReadTimeout("timed out", request=request)
        )
    }
    client = make_client(ServiceRouterTransport(apps={}, errors=errors))
    try:
        response = client.get("/api/v1/reservas")
    finally:
        client.__exit__(None, None, None)
    assert response.status_code == 504
    assert response.json() == {
        "detail": "Service 'reservas' did not respond in time",
        "service": "reservas",
    }


def test_gateway_unknown_route_returns_json_404():
    """Paths outside the routing map get a consistent JSON 404."""
    client = make_client(ServiceRouterTransport())
    try:
        response = client.get("/api/v1/desconocido")
    finally:
        client.__exit__(None, None, None)
    assert response.status_code == 404
    assert "detail" in response.json()


# ---------------------------------------------------------------------------
# Authentication routing (Sprint 2)
# ---------------------------------------------------------------------------


def test_gateway_routes_auth_login_to_clientes(patch_service_db):
    """POST /api/v1/auth/login is proxied to the clientes microservice."""
    # No matching user in the fake: the service answers 401, which proves
    # the request reached the real login endpoint through the gateway.
    patch_service_db(clientes_main, one_results=[None])
    client = make_client(ServiceRouterTransport())
    try:
        response = client.post(
            "/api/v1/auth/login",
            json={"correo": "nadie@puntoysal.test", "password": "incorrecta"},
        )
    finally:
        client.__exit__(None, None, None)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_gateway_forwards_authorization_header(patch_service_db, admin_headers):
    """The Authorization header reaches the microservice untouched."""
    patch_service_db(clientes_main, all_results=[[]])
    client = make_client(ServiceRouterTransport())
    try:
        with_token = client.get("/api/v1/clientes", headers=admin_headers)
    finally:
        client.__exit__(None, None, None)
    assert with_token.status_code == 200
    assert with_token.json() == {"data": []}


def test_gateway_cannot_bypass_authorization(patch_service_db):
    """No token through the gateway still fails at the microservice (401).

    The gateway performs no authentication of its own, so a request
    without credentials is forwarded as-is and the microservice rejects
    it with 401: routing through the gateway never bypasses the rules.
    """
    patch_service_db(clientes_main, all_results=[[]])
    client = make_client(ServiceRouterTransport())
    try:
        response = client.get("/api/v1/clientes")
    finally:
        client.__exit__(None, None, None)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
    assert response.headers.get("www-authenticate") == "Bearer"


def test_gateway_auth_methods_are_post_only(patch_service_db):
    """The auth routes only accept POST (login); GET is not routable."""
    patch_service_db(clientes_main, all_results=[[]])
    client = make_client(ServiceRouterTransport())
    try:
        response = client.get("/api/v1/auth/login")
    finally:
        client.__exit__(None, None, None)
    assert response.status_code == 405


def test_gateway_openapi_available():
    """The gateway exposes its own Swagger documentation."""
    client = make_client(ServiceRouterTransport())
    try:
        response = client.get("/openapi.json")
        docs = client.get("/docs")
    finally:
        client.__exit__(None, None, None)
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health" in paths
    assert "/api/v1/clientes/{path}" in paths
    assert "/api/v1/reservas/{path}" in paths
    assert "/api/v1/catalogo/{path}" in paths
    assert docs.status_code == 200
