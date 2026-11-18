"""Gateway <-> auth tests: POST /api/v1/auth/login proxied in-process.

Reuses the test_gateway transport (routes by origin to real ASGI apps);
the auth service origin (8004) is part of ``SERVICE_APPS``, so these
tests need no sockets and no database.
"""

import httpx

from services.auth.app import main as auth_main
from shared.auth import decode_token, hash_password
from test_gateway import SERVICE_APPS, ServiceRouterTransport, make_client

AUTH_ORIGIN = "http://localhost:8004"

VALID_PASSWORD = "correct-password"
VALID_HASH = hash_password(VALID_PASSWORD)
CORREO = "admin.prueba@puntoysal.test"

ADMIN_ROW = {
    "id_usuario": 1,
    "correo": CORREO,
    "password_hash": VALID_HASH,
    "rol": "administrador",
    "activo": True,
    # Profile-link columns of the login query (LEFT JOINs): the token
    # must carry the administrator profile id.
    "id_cliente": None,
    "id_administrador": 1,
}


def test_gateway_proxies_login_to_auth_service(patch_service_db):
    """POST /api/v1/auth/login reaches the auth service through the gateway."""
    patch_service_db(auth_main, one_results=[ADMIN_ROW])
    client = make_client(ServiceRouterTransport(apps=SERVICE_APPS))
    try:
        response = client.post(
            "/api/v1/auth/login",
            json={"correo": CORREO, "password": VALID_PASSWORD},
        )
    finally:
        client.__exit__(None, None, None)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["rol"] == "administrador"
    # The token carries the canonical claims: identity, role, profile
    # id and the issued-at/expiration timestamps.
    payload = decode_token(body["access_token"])
    assert payload["sub"] == "1"
    assert payload["rol"] == "administrador"
    assert payload["id_administrador"] == 1
    assert payload["exp"] > payload["iat"]
    # No credential material leaks in the response.
    assert VALID_PASSWORD not in response.text
    assert VALID_HASH not in response.text


def test_gateway_login_401_passes_through(patch_service_db):
    """A downstream 401 (bad credentials) passes through untouched."""
    patch_service_db(auth_main, one_results=[ADMIN_ROW])
    client = make_client(ServiceRouterTransport(apps=SERVICE_APPS))
    try:
        response = client.post(
            "/api/v1/auth/login",
            json={"correo": CORREO, "password": "wrong-password"},
        )
    finally:
        client.__exit__(None, None, None)
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


def test_gateway_login_returns_503_when_auth_unavailable():
    """Unreachable auth service produces the controlled JSON 503."""
    errors = {AUTH_ORIGIN: (lambda request: httpx.ConnectError("refused", request=request))}
    client = make_client(ServiceRouterTransport(apps={}, errors=errors))
    try:
        response = client.post(
            "/api/v1/auth/login",
            json={"correo": CORREO, "password": VALID_PASSWORD},
        )
    finally:
        client.__exit__(None, None, None)
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Service 'auth' is unavailable",
        "service": "auth",
    }
    # No internal URLs or stack traces leak to the caller.
    assert "localhost" not in response.text
    assert "Traceback" not in response.text


def test_gateway_has_post_login_route():
    """The gateway's OpenAPI exposes the POST login route (and only POST)."""
    client = make_client(ServiceRouterTransport(apps=SERVICE_APPS))
    try:
        docs = client.get("/openapi.json")
    finally:
        client.__exit__(None, None, None)
    assert docs.status_code == 200
    methods = docs.json()["paths"]["/api/v1/auth/login"]
    assert list(methods.keys()) == ["post"]
